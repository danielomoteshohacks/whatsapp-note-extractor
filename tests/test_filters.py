# tests/test_filters.py
#
# These tests verify that every filter function in parser/filters.py
# returns the correct results for known inputs.
#
# We use controlled sample messages that contain patterns each filter
# is designed to catch — both standard English and Nigerian Pidgin expressions.

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from parser.whatsapp_parser import Message
from parser.filters import (
    filter_links,
    filter_deadlines,
    filter_announcements,
    filter_questions,
    filter_media,
    apply_filter,
)

# Helper to create a Message quickly
def msg(content, is_media=False, is_system=False, sender="Daniel"):
    return Message(
        timestamp=datetime(2026, 4, 20, 10, 0),
        sender=sender,
        content=content,
        is_media=is_media,
        is_system=is_system
    )

# Attach empty entities and key_phrases to all messages
def prepare(messages):
    for m in messages:
        if not hasattr(m, 'entities'):
            m.entities = []
        if not hasattr(m, 'key_phrases'):
            m.key_phrases = []
    return messages


# --- TEST 1: LINKS FILTER ---
def test_filter_links():
    messages = prepare([
        msg("Check the portal at www.unilag.edu.ng for your result"),
        msg("Please submit before Friday"),
        msg("https://forms.gle/abc123 fill this form"),
        msg("Good morning everyone"),
        msg("The link is on the school website"),
    ])

    results = filter_links(messages)
    contents = [m.content for m in results]

    assert any("www.unilag.edu.ng" in c for c in contents), "Should catch www URL"
    assert any("https://forms.gle" in c for c in contents), "Should catch https URL"
    assert not any("Good morning" in c for c in contents), "Should not catch greetings"
    print("[PASSED] Test 1: filter_links works correctly")


# --- TEST 2: DEADLINES FILTER ---
def test_filter_deadlines():
    messages = prepare([
        msg("Submit your assignment before Friday 5pm"),
        msg("Abeg make sure una submit before the portal closes tonight"),
        msg("Good afternoon everyone"),
        msg("The deadline for TMA is tomorrow midnight"),
        msg("How far guys"),
    ])

    # Attach DateTime entities to deadline messages
    from ai.entity_extractor import Entity
    messages[0].entities = [Entity(text="Friday 5pm", category="DateTime", subcategory="", confidence=0.99)]
    messages[1].entities = [Entity(text="tonight", category="DateTime", subcategory="", confidence=0.95)]
    messages[3].entities = [Entity(text="tomorrow midnight", category="DateTime", subcategory="", confidence=0.99)]

    results = filter_deadlines(messages)
    contents = [m.content for m in results]

    assert any("Friday 5pm" in c for c in contents), "Should catch English deadline"
    assert any("portal closes" in c for c in contents), "Should catch Nigerian Pidgin deadline"
    assert any("TMA" in c for c in contents), "Should catch TMA deadline"
    assert not any("Good afternoon" in c for c in contents), "Should not catch greetings"
    print("[PASSED] Test 2: filter_deadlines works correctly")


# --- TEST 3: ANNOUNCEMENTS FILTER ---
def test_filter_announcements():
    messages = prepare([
        msg("Attention everyone, the exam timetable has been released"),
        msg("Make una note say the venue don change to LT1"),
        msg("How far"),
        msg("Guys, important update — registration closes tomorrow"),
        msg("Lol okay"),
    ])

    results = filter_announcements(messages)
    contents = [m.content for m in results]

    assert any("exam timetable" in c for c in contents), "Should catch formal announcement"
    assert any("venue don change" in c for c in contents), "Should catch Nigerian Pidgin announcement"
    assert not any("How far" in c for c in contents), "Should not catch casual greetings"
    print("[PASSED] Test 3: filter_announcements works correctly")


# --- TEST 4: QUESTIONS FILTER ---
def test_filter_questions():
    messages = prepare([
        msg("Who has the timetable for tomorrow?"),
        msg("Abeg who get the assignment question?"),
        msg("Wetin be the venue for the test?"),
        msg("Good morning everyone"),
        msg("Shey anybody know when result go drop?"),
    ])

    results = filter_questions(messages)
    contents = [m.content for m in results]

    assert any("timetable" in c for c in contents), "Should catch English question"
    assert any("assignment question" in c for c in contents), "Should catch Pidgin question with abeg"
    assert any("venue" in c for c in contents), "Should catch Pidgin question with wetin"
    assert any("result" in c for c in contents), "Should catch Pidgin question with shey"
    assert not any("Good morning" in c for c in contents), "Should not catch greetings"
    print("[PASSED] Test 4: filter_questions works correctly")


# --- TEST 5: MEDIA FILTER ---
def test_filter_media():
    messages = prepare([
        msg("<Media omitted>", is_media=True),
        msg("Please check the document I just sent"),
        msg("<Media omitted>", is_media=True),
        msg("Good evening"),
        msg("image omitted", is_media=True),
    ])

    results = filter_media(messages)

    assert len(results) == 3, f"Should return 3 media messages, got {len(results)}"
    assert all(m.is_media for m in results), "All results should be media messages"
    print("[PASSED] Test 5: filter_media works correctly")


# --- TEST 6: APPLY FILTER ---
def test_apply_filter():
    messages = prepare([
        msg("Who has the notes?"),
        msg("Submit before Friday 5pm"),
        msg("<Media omitted>", is_media=True),
    ])

    messages[1].entities = []
    from ai.entity_extractor import Entity
    messages[1].entities = [Entity(text="Friday 5pm", category="DateTime", subcategory="", confidence=0.99)]

    assert len(apply_filter("questions", messages)) > 0, "questions filter should return results"
    assert len(apply_filter("media", messages)) > 0, "media filter should return results"
    assert len(apply_filter("invalid", messages)) == 0, "invalid filter should return empty list"
    print("[PASSED] Test 6: apply_filter routes correctly")


# --- RUN ALL TESTS ---
if __name__ == "__main__":
    print("Running filter tests...\n")
    test_filter_links()
    test_filter_deadlines()
    test_filter_announcements()
    test_filter_questions()
    test_filter_media()
    test_apply_filter()
    print("\nAll filter tests complete.")
