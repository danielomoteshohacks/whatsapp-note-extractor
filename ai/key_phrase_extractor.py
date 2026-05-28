# ai/key_phrase_extractor.py
#
# This file connects to Azure AI Language and extracts key phrases from
# WhatsApp messages. Key phrase extraction is different from entity extraction —
# instead of identifying specific named things like dates and phone numbers,
# it identifies the main topics and concepts in a piece of text.
#
# For example:
#   "Submit your ENG 301 assignment before Friday 5pm through the portal"
#   Key phrases: ["ENG 301 assignment", "Friday 5pm", "portal"]
#
# This gives us a topic index that works independently of exact keywords.
# A message about "the physics practical" and another about "PHY 301 lab work"
# might share key phrases even though they use different words.
#
# The key phrases are stored on each Message object as a list of strings.
# They are used by the filter system on Day 5 and the search index on Day 7.

import os
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from parser.whatsapp_parser import Message

load_dotenv()


# ─── AZURE CLIENT ─────────────────────────────────────────────────────────────
# Reuses the same Azure AI Language resource as the entity extractor.
# Both NER and key phrase extraction are features of the same service.

def get_language_client() -> TextAnalyticsClient:
    key = os.getenv("AZURE_LANGUAGE_KEY")
    endpoint = os.getenv("AZURE_LANGUAGE_ENDPOINT")

    if not key or not endpoint:
        raise ValueError(
            "AZURE_LANGUAGE_KEY and AZURE_LANGUAGE_ENDPOINT must be set in your .env file."
        )

    return TextAnalyticsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )


# ─── BATCH SPLITTER ───────────────────────────────────────────────────────────
# Same batch logic as the entity extractor — free tier limit is 5 per call.

def split_into_batches(items: list, batch_size: int = 5) -> list:
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


# ─── KEY PHRASE EXTRACTOR ─────────────────────────────────────────────────────
# Takes a list of Message objects and returns the same list with a
# key_phrases attribute attached to each message.
#
# We skip the same message types as the entity extractor — media, system,
# and very short messages — for the same reasons: no meaningful content,
# would waste API quota.

def extract_key_phrases(messages: list[Message]) -> list[Message]:
    client = get_language_client()

    # Only process messages with real text content
    processable = [
        m for m in messages
        if not m.is_media and not m.is_system and len(m.content.strip()) >= 10
    ]

    # Build a lookup from content to message object
    content_to_message = {m.content: m for m in processable}
    texts = [m.content for m in processable]
    batches = split_into_batches(texts, batch_size=5)

    print(f"[Key Phrase Extractor] Processing {len(processable)} messages in {len(batches)} batches...")

    all_results = []

    for i, batch in enumerate(batches):
        try:
            # extract_key_phrases returns one result per document
            results = client.extract_key_phrases(batch)
            all_results.extend(results)
        except Exception as e:
            print(f"[Key Phrase Extractor] Batch {i+1} failed: {e}")
            all_results.extend([None] * len(batch))

    # Attach key phrases to each message
    for text, result in zip(texts, all_results):
        if result is None or result.is_error:
            continue

        message = content_to_message.get(text)
        if not message:
            continue

        # key_phrases is a list of strings — the main topics Azure found
        message.key_phrases = list(result.key_phrases)

    # Attach empty list to all messages that were skipped or had no results
    for m in messages:
        if not hasattr(m, 'key_phrases'):
            m.key_phrases = []

    print(f"[Key Phrase Extractor] Done.")
    return messages