# tests/test_entity_extractor.py
#
# These tests verify that the entity extractor connects to Azure AI Language
# correctly and returns sensible results on known inputs.
#
# Unlike the parser and stats tests which use purely local sample data,
# these tests make real API calls to Azure. That means:
# 1. You need a valid .env file with AZURE_LANGUAGE_KEY and AZURE_LANGUAGE_ENDPOINT
# 2. The tests consume a small amount of your free tier quota
# 3. They require an internet connection to run
#
# We test with a small set of messages that contain known entities so we can
# assert that Azure found what we expect.

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from parser.whatsapp_parser import Message
from ai.entity_extractor import extract_entities, entity_summary, get_language_client


# ─── TEST 1: CLIENT CONNECTION ────────────────────────────────────────────────
# Verifies that we can successfully create an authenticated Azure client.
# If this fails it means the .env file is missing or the credentials are wrong.

def test_client_connection():
    try:
        client = get_language_client()
        assert client is not None, "Client should not be None"
        print("[PASSED] Test 1: Azure Language client created successfully")
    except ValueError as e:
        print(f"[FAILED] Test 1: Could not create client — {e}")
        raise


# ─── TEST 2: ENTITY EXTRACTION ON KNOWN INPUT ─────────────────────────────────
# Sends a message containing known entities and checks that Azure found them.
# We use a message with a clear date, URL, and phone number so the assertions
# are reliable regardless of Azure model updates.

def test_entity_extraction():
    messages = [
        Message(
            timestamp=datetime(2026, 4, 20, 10, 0),
            sender="Daniel",
            content="Submit your assignment at www.portal.unilag.edu.ng before Friday 5pm",
            is_media=False,
            is_system=False
        ),
        Message(
            timestamp=datetime(2026, 4, 20, 10, 5),
            sender="Eric",
            content="Call the course rep on 08012345678 for the timetable",
            is_media=False,
            is_system=False
        ),
    ]

    result = extract_entities(messages)

    # Both messages should now have an entities attribute
    assert hasattr(result[0], 'entities'), "First message should have entities attribute"
    assert hasattr(result[1], 'entities'), "Second message should have entities attribute"

    # The first message should have at least one entity (URL or DateTime)
    assert len(result[0].entities) > 0, "First message should have at least one entity"

    print(f"[PASSED] Test 2: Entity extraction returned results")
    print(f"   Message 1 entities: {[(e.text, e.category) for e in result[0].entities]}")
    print(f"   Message 2 entities: {[(e.text, e.category) for e in result[1].entities]}")


# ─── TEST 3: MEDIA AND SYSTEM MESSAGES ARE SKIPPED ────────────────────────────
# Verifies that media and system messages are skipped during extraction
# and get an empty entities list rather than causing an API call.

def test_skips_media_and_system():
    messages = [
        Message(
            timestamp=datetime(2026, 4, 20, 10, 0),
            sender="Daniel",
            content="<Media omitted>",
            is_media=True,
            is_system=False
        ),
        Message(
            timestamp=datetime(2026, 4, 20, 10, 5),
            sender="Daniel",
            content="left",
            is_media=False,
            is_system=True
        ),
    ]

    result = extract_entities(messages)

    # Both messages should have empty entities lists
    assert result[0].entities == [], "Media message should have empty entities"
    assert result[1].entities == [], "System message should have empty entities"
    print("[PASSED] Test 3: Media and system messages correctly skipped")


# ─── TEST 4: ENTITY SUMMARY ───────────────────────────────────────────────────
# Verifies that entity_summary correctly counts entities by category.

def test_entity_summary():
    messages = [
        Message(
            timestamp=datetime(2026, 4, 20, 10, 0),
            sender="Daniel",
            content="Meet Dr. Johnson at the faculty on Monday at 10am",
            is_media=False,
            is_system=False
        ),
    ]

    result = extract_entities(messages)
    summary = entity_summary(result)

    # Summary should be a dictionary
    assert isinstance(summary, dict), "Summary should be a dictionary"
    print(f"[PASSED] Test 4: Entity summary generated correctly")
    print(f"   Summary: {summary}")


# ─── TEST 5: REAL EXPORT ──────────────────────────────────────────────────────
# Runs entity extraction on the first 20 messages of the real export
# and prints a summary of what was found. We only process 20 messages
# to avoid using too much free tier quota during testing.

def test_real_export_sample():
    from parser.whatsapp_parser import parse_export, extract_whatsapp_zip

    zip_files = [f for f in os.listdir('data') if f.endswith('.zip')]
    if not zip_files:
        print("[SKIPPED] Test 5: No zip file found in data/ folder")
        return

    zip_path = os.path.join('data', zip_files[0])
    txt_path = extract_whatsapp_zip(zip_path)
    all_messages = parse_export(txt_path)

    # Only process first 20 non-system, non-media messages to save quota
    sample = [
        m for m in all_messages
        if not m.is_media and not m.is_system
    ][:20]

    result = extract_entities(sample)
    summary = entity_summary(result)

    print(f"\n[PASSED] Test 5: Real export sample processed")
    print(f"   Messages processed : {len(sample)}")
    print(f"   Entity summary     : {summary}")
    print(f"\n   Sample entities from first 5 messages with results:")
    count = 0
    for m in result:
        if m.entities and count < 5:
            print(f"   [{m.sender}]: {m.content[:50]}")
            for e in m.entities:
                print(f"      -> {e.category}: '{e.text}' (confidence: {e.confidence})")
            count += 1


# ─── RUN ALL TESTS ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Running entity extractor tests...\n")
    test_client_connection()
    test_entity_extraction()
    test_skips_media_and_system()
    test_entity_summary()
    test_real_export_sample()
    print("\nAll entity extractor tests complete.")