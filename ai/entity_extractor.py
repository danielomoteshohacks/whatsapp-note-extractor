# ai/entity_extractor.py
#
# This file connects to Azure AI Language and runs Named Entity Recognition (NER)
# on WhatsApp messages. NER is the process of automatically identifying and
# categorising key pieces of information in text — dates, times, URLs, phone
# numbers, person names, and so on.
#
# The output of this file is the same list of Message objects that the parser
# produced, but each message now has an extra field: a list of entities found
# in its content. This entity metadata is what powers the smart filters on Day 5
# and the search indexing on Day 7.
#
# Azure AI Language processes text in batches of up to 5 documents at a time
# on the free tier. We handle this by splitting messages into batches and
# processing each batch separately, then reassembling the results.

import os
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from parser.whatsapp_parser import Message
from dataclasses import dataclass, field

# Load environment variables from the .env file.
# This is how we read AZURE_LANGUAGE_KEY and AZURE_LANGUAGE_ENDPOINT
# without hardcoding them in the source code.
load_dotenv()


# ─── ENTITY OBJECT ────────────────────────────────────────────────────────────
# Represents a single entity extracted from a message.
# For example, from "Submit ENG 301 assignment by Friday 5pm" Azure might extract:
#   Entity(text="Friday 5pm", category="DateTime", subcategory="DateRange")
#   Entity(text="ENG 301", category="Organization")

@dataclass
class Entity:
    text: str          # The actual text of the entity as it appeared in the message
    category: str      # The type of entity: DateTime, Person, URL, PhoneNumber, etc.
    subcategory: str   # A more specific classification within the category
    confidence: float  # How confident Azure is in this extraction (0.0 to 1.0)


# ─── AZURE CLIENT SETUP ───────────────────────────────────────────────────────
# Creates and returns an authenticated Azure AI Language client.
# The client is what we use to make API calls to Azure.
# AzureKeyCredential wraps the API key in the format Azure expects.
# This function is called once when the extractor is first used.

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
# Azure AI Language's free tier (F0) processes a maximum of 5 documents
# per API call. This function splits a list into chunks of the given size
# so we can process large message lists without hitting that limit.
# For example, a list of 1800 messages becomes 360 batches of 5.

def split_into_batches(items: list, batch_size: int = 5) -> list:
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


# ─── ENTITY EXTRACTOR ─────────────────────────────────────────────────────────
# The main function. Takes a list of Message objects and returns the same list
# with entities attached to each message.
#
# We skip media messages and system messages because they have no meaningful
# text content to extract entities from — "<Media omitted>" would just waste
# API quota. We also skip very short messages (under 10 characters) for the
# same reason.
#
# The confidence_threshold parameter filters out low-confidence extractions.
# Azure sometimes identifies entities it is not sure about — a threshold of
# 0.7 means we only keep entities Azure is at least 70% confident about.

def extract_entities(
    messages: list[Message],
    confidence_threshold: float = 0.7
) -> list[Message]:

    client = get_language_client()

    # Separate messages that are worth processing from those that are not
    processable = [
        m for m in messages
        if not m.is_media and not m.is_system and len(m.content.strip()) >= 10
    ]

    # Build a lookup from message content to the message object.
    # We need this to match Azure's results back to the original messages
    # after processing.
    # Note: if two messages have identical content, the last one wins in
    # this lookup. This is an acceptable trade-off for now.
    content_to_message = {m.content: m for m in processable}

    # Extract just the text content for Azure to process
    texts = [m.content for m in processable]

    # Split into batches of 5 (free tier limit)
    batches = split_into_batches(texts, batch_size=5)

    print(f"[Entity Extractor] Processing {len(processable)} messages in {len(batches)} batches...")

    all_results = []

    for i, batch in enumerate(batches):
        try:
            # Send the batch to Azure AI Language for NER
            # recognize_entities returns one result object per document
            results = client.recognize_entities(batch)
            all_results.extend(results)

        except Exception as e:
            # If a batch fails, log the error and continue with the next batch
            # rather than crashing the entire extraction process
            print(f"[Entity Extractor] Batch {i+1} failed: {e}")
            # Add None placeholders so our indexing stays aligned
            all_results.extend([None] * len(batch))

    # Match results back to messages and attach entities
    for text, result in zip(texts, all_results):
        if result is None or result.is_error:
            continue

        message = content_to_message.get(text)
        if not message:
            continue

        # Filter by confidence threshold and convert to Entity objects
        entities = [
            Entity(
                text=entity.text,
                category=entity.category,
                subcategory=entity.subcategory or "",
                confidence=round(entity.confidence_score, 3)
            )
            for entity in result.entities
            if entity.confidence_score >= confidence_threshold
        ]

        # Attach the entities list to the message object as a new attribute.
        # Python dataclasses do not have an entities field by default —
        # we add it dynamically here. Day 5 filters and Day 7 search indexing
        # will read this field.
        message.entities = entities

    # For messages that were skipped (media, system, too short),
    # attach an empty entities list so all messages have the field
    for m in messages:
        if not hasattr(m, 'entities'):
            m.entities = []

    print(f"[Entity Extractor] Done.")
    return messages


# ─── ENTITY SUMMARY ───────────────────────────────────────────────────────────
# A helper function that takes an entity-enriched message list and returns
# a summary of what was found — useful for debugging and for the dashboard.
# Returns a dict with counts per entity category.

def entity_summary(messages: list[Message]) -> dict:
    summary = {}
    for m in messages:
        for entity in getattr(m, 'entities', []):
            summary[entity.category] = summary.get(entity.category, 0) + 1
    return dict(sorted(summary.items(), key=lambda x: x[1], reverse=True))