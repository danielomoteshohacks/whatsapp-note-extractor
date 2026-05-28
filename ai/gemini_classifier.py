# ai/gemini_classifier.py
#
# This file uses Google Gemini to classify WhatsApp messages into categories.
# It works alongside the keyword-based filters in parser/filters.py —
# the keyword filters run first as a fast pass, and Gemini handles the
# messages that are ambiguous or use language patterns the keywords miss.
#
# Uses the new google-genai SDK (google.genai) with gemini-2.0-flash.

import os
import json
from google import genai
from dotenv import load_dotenv
from parser.whatsapp_parser import Message

load_dotenv()


# ─── GEMINI CLIENT SETUP ──────────────────────────────────────────────────────
def setup_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY must be set in your .env file.")
    client = genai.Client(api_key=api_key)
    return client


# ─── BATCH CLASSIFIER ─────────────────────────────────────────────────────────
# Sends a batch of messages to Gemini and asks it to classify each one.
# Returns a list of category labels in the same order as the input messages.

def classify_messages_batch(messages: list[Message], client) -> list[str]:
    if not messages:
        return []

    message_lines = []
    for i, m in enumerate(messages):
        content = m.content[:200] if len(m.content) > 200 else m.content
        message_lines.append(f"{i+1}. {content}")

    messages_text = "\n".join(message_lines)

    prompt = f"""You are classifying WhatsApp messages from a Nigerian university student group chat.
The messages may be in English, Nigerian Pidgin, Yoruba/Igbo/Hausa mixed with English, or informal student slang.

Classify each message into EXACTLY ONE of these categories:
- "question": asking for information, help, confirmation, or clarification. Includes Pidgin questions like "abeg who get", "wetin be", "shey anybody know", "any update", etc.
- "deadline": mentions a submission deadline, due date, time-sensitive action, exam date, registration closing. Includes "submit before", "e go close", "last chance", "abeg do am fast", etc.
- "announcement": sharing information, updates, changes, reminders with the group. Includes "make una note", "important update", "dem don change", "result don drop", etc.
- "link": contains or refers to a URL, website, portal, or online resource.
- "media": refers to a shared file, image, video, audio, or document.
- "other": casual conversation, greetings, reactions, jokes, that do not fit the above.

Messages to classify:
{messages_text}

Respond ONLY with a valid JSON array of strings, one label per message, in the same order.
Example: ["question", "announcement", "other", "deadline", "link"]
No explanation, no markdown, no extra text. Just the JSON array."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        labels = json.loads(raw)

        if len(labels) != len(messages):
            return ["other"] * len(messages)

        return labels

    except Exception as e:
        print(f"[Gemini Classifier] Batch classification failed: {e}")
        return ["other"] * len(messages)


# ─── ENHANCE FILTERS WITH GEMINI ──────────────────────────────────────────────
def gemini_enhance_filter(
    all_messages: list[Message],
    keyword_results: list[Message],
    target_category: str,
    batch_size: int = 20
) -> list[Message]:

    try:
        client = setup_gemini()
    except ValueError as e:
        print(f"[Gemini Classifier] Skipping — {e}")
        return keyword_results

    keyword_result_ids = {id(m) for m in keyword_results}
    uncaught = [
        m for m in all_messages
        if id(m) not in keyword_result_ids
        and not m.is_media
        and not m.is_system
        and len(m.content.strip()) >= 15
    ]

    if not uncaught:
        return keyword_results

    print(f"[Gemini Classifier] Classifying {len(uncaught)} uncaught messages for '{target_category}'...")

    gemini_matches = []
    for i in range(0, len(uncaught), batch_size):
        batch = uncaught[i:i + batch_size]
        labels = classify_messages_batch(batch, client)

        for message, label in zip(batch, labels):
            if label.lower() == target_category.lower():
                gemini_matches.append(message)

    print(f"[Gemini Classifier] Found {len(gemini_matches)} additional matches.")

    existing_ids = {id(m) for m in keyword_results}
    for m in gemini_matches:
        if id(m) not in existing_ids:
            keyword_results.append(m)
            existing_ids.add(id(m))

    keyword_results.sort(
        key=lambda m: m.timestamp or __import__('datetime').datetime.min
    )

    return keyword_results