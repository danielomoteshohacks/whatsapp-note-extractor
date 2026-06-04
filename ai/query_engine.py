# ai/query_engine.py
#
# Retrieval Augmented Generation (RAG) query engine using Gemini.
# 
# How it works:
# 1. User types a free-form question
# 2. We do a fast keyword pre-filter to find the top 50 most relevant messages
# 3. Those messages are passed to Gemini as context
# 4. Gemini reads them all and writes a synthesized, human-readable answer
# 5. Returns both the answer and the source messages it drew from
#
# This is true AI reasoning — not keyword matching. Gemini reads the actual
# chat content and answers like a knowledgeable human assistant who has
# read through the entire conversation.

import os
import re
from google import genai
from dotenv import load_dotenv
from parser.whatsapp_parser import Message

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_CONTEXT_MESSAGES = 60  # Maximum messages to send to Gemini as context


def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY must be set in your .env file.")
    return genai.Client(api_key=api_key)


# ─── FAST KEYWORD PRE-FILTER ──────────────────────────────────────────────────
# Before sending to Gemini, we narrow down the 1,800 messages to the most
# relevant ones. This keeps the context window manageable and focused.
# We extract simple keywords from the query and score each message.

def prefilter_messages(query: str, messages: list[Message], top_n: int = MAX_CONTEXT_MESSAGES) -> list[Message]:
    # Extract meaningful words from the query (3+ characters, not stopwords)
    stopwords = {"the", "and", "for", "are", "was", "were", "this", "that",
                 "with", "from", "have", "has", "had", "about", "what", "show",
                 "tell", "give", "find", "need", "want", "information", "details",
                 "messages", "chat", "group", "please", "abeg", "me", "us", "all"}

    words = [w.lower() for w in re.findall(r'\b\w{3,}\b', query.lower())
             if w.lower() not in stopwords]

    if not words:
        # If no keywords extracted, return most recent non-system messages
        return [m for m in messages if not m.is_system and not m.is_media][:top_n]

    # Score each message
    scored = []
    for m in messages:
        if m.is_system:
            continue

        score = 0
        content_lower = m.content.lower()

        # Score by keyword matches in content
        for word in words:
            if word in content_lower:
                score += 2

        # Score by key phrase matches (higher weight)
        for phrase in getattr(m, 'key_phrases', []):
            for word in words:
                if word in phrase.lower():
                    score += 3

        # Score by entity matches
        for entity in getattr(m, 'entities', []):
            for word in words:
                if word in entity.text.lower():
                    score += 2

        if score > 0:
            scored.append((score, m))

    # Sort by score and return top_n
    scored.sort(key=lambda x: x[0], reverse=True)
    top_messages = [m for score, m in scored[:top_n]]

    # If we found fewer than 10 relevant messages, add some recent context
    if len(top_messages) < 10:
        recent = [m for m in messages
                  if not m.is_system and id(m) not in {id(x) for x in top_messages}][-20:]
        top_messages.extend(recent)

    return top_messages


# ─── FORMAT MESSAGES FOR GEMINI CONTEXT ───────────────────────────────────────
# Formats the selected messages into a readable context string for Gemini.
# Each message shows the sender, timestamp, and content.

def format_context(messages: list[Message]) -> str:
    lines = []
    for m in messages:
        timestamp = m.timestamp.strftime('%d %b %Y, %I:%M %p') if m.timestamp else "Unknown time"
        lines.append(f"[{timestamp}] {m.sender}: {m.content}")
    return "\n".join(lines)


# ─── GEMINI RAG ANSWER GENERATION ─────────────────────────────────────────────
# Sends the user's question and relevant chat messages to Gemini.
# Gemini synthesizes a human-readable answer from the chat context.

def generate_answer(query: str, context_messages: list[Message]) -> str:
    client = get_gemini_client()
    context = format_context(context_messages)

    prompt = f"""You are a smart, friendly assistant helping a Nigerian university student get quick answers from their WhatsApp group chat.

Answer the question below using ONLY information from the provided chat messages. Write like a knowledgeable friend texting back — warm, direct, human. Not robotic, not formal.

Rules:
- Start directly with the answer. Never say "Based on the messages" or "I found" or "Here's what I found".
- Use line breaks between points for readability. Not long paragraphs.
- Bold the most important words or phrases using **bold**.
- Include every specific detail that matters: names, dates, amounts, links, deadlines, account numbers, course codes.
- If something is not in the chat, say it clearly in one short sentence.
- Understand and interpret Nigerian Pidgin naturally — do not translate it, just understand it.
- Maximum 150 words. Be tight.

QUESTION: {query}

CHAT MESSAGES:
{context}

ANSWER:"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Query Engine] Answer generation failed: {e}")
        return "I was unable to generate an answer at this time. Please try again."


# ─── MAIN QUERY FUNCTION ──────────────────────────────────────────────────────
# Called from the Flask route.
# Returns (answer, source_messages) tuple.
# answer — Gemini's synthesized response
# source_messages — the messages Gemini used as context (shown below the answer)

def run_query(query: str, messages: list[Message]) -> tuple:
    if not query or not query.strip():
        return "No query provided.", []

    print(f"[Query Engine] Query: {query}")

    # Step 1: Fast pre-filter to find most relevant messages
    relevant_messages = prefilter_messages(query, messages)
    print(f"[Query Engine] Found {len(relevant_messages)} relevant messages")

    # Step 2: Generate synthesized answer with Gemini
    answer = generate_answer(query, relevant_messages)
    print(f"[Query Engine] Answer generated")

    return answer, relevant_messages[:20]  # Return top 20 as source messages