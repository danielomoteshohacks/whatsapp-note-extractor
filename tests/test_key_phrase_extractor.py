# tests/test_key_phrase_extractor.py
#
# These tests verify that the key phrase extractor connects to Azure AI Language
# correctly and returns sensible results on known inputs.
# Like test_entity_extractor.py, these make real API calls to Azure.

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from parser.whatsapp_parser import Message
from ai.key_phrase_extractor import extract_key_phrases


def msg(content, is_media=False, is_system=False, sender="Daniel"):
    return Message(
        timestamp=datetime(2026, 4, 20, 10, 0),
        sender=sender,
        content=content,
        is_media=is_media,
        is_system=is_system
    )


# --- TEST 1: KEY PHRASES ATTACHED ---
def test_key_phrases_attached():
    messages = [
        msg("Submit your ENG 301 assignment before Friday 5pm through the portal"),
        msg("The exam timetable for second semester has been released on the school portal"),
    ]

    result = extract_key_phrases(messages)

    assert hasattr(result[0], 'key_phrases'), "First message should have key_phrases attribute"
    assert hasattr(result[1], 'key_phrases'), "Second message should have key_phrases attribute"
    assert len(result[0].key_phrases) > 0, "First message should have at least one key phrase"
    print(f"[PASSED] Test 1: Key phrases attached successfully")
    print(f"   Message 1 phrases: {result[0].key_phrases}")
    print(f"   Message 2 phrases: {result[1].key_phrases}")


# --- TEST 2: MEDIA AND SYSTEM MESSAGES SKIPPED ---
def test_skips_media_and_system():
    messages = [
        msg("<Media omitted>", is_media=True),
        msg("left", is_system=True),
    ]

    result = extract_key_phrases(messages)

    assert result[0].key_phrases == [], "Media message should have empty key_phrases"
    assert result[1].key_phrases == [], "System message should have empty key_phrases"
    print("[PASSED] Test 2: Media and system messages correctly skipped")


# --- TEST 3: REAL EXPORT SAMPLE ---
def test_real_export_sample():
    from parser.whatsapp_parser import parse_export, extract_whatsapp_zip

    zip_files = [f for f in os.listdir('data') if f.endswith('.zip')]
    if not zip_files:
        print("[SKIPPED] Test 3: No zip file found in data/ folder")
        return

    zip_path = os.path.join('data', zip_files[0])
    txt_path = extract_whatsapp_zip(zip_path)
    all_messages = parse_export(txt_path)

    sample = [
        m for m in all_messages
        if not m.is_media and not m.is_system
    ][:10]

    result = extract_key_phrases(sample)

    print(f"\n[PASSED] Test 3: Real export sample processed")
    print(f"   Messages processed: {len(sample)}")
    for m in result[:3]:
        if m.key_phrases:
            print(f"   [{m.sender}]: {m.content[:50]}")
            print(f"      Phrases: {m.key_phrases}")


# --- RUN ALL TESTS ---
if __name__ == "__main__":
    print("Running key phrase extractor tests...\n")
    test_key_phrases_attached()
    test_skips_media_and_system()
    test_real_export_sample()
    print("\nAll key phrase extractor tests complete.")
