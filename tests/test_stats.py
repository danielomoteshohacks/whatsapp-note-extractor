# tests/test_stats.py
#
# These tests verify that every function in dashboard/stats.py
# returns the correct output for known inputs.
#
# The approach is the same as test_parser.py — we create controlled
# sample data, feed it into each function, and assert the output
# is exactly what we expect. This way if anyone changes the stats
# logic later and accidentally breaks something, these tests will
# catch it immediately.

import sys
import os

# Tell Python where to find the project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from parser.whatsapp_parser import Message
from dashboard.stats import (
    total_messages,
    unique_members,
    active_days,
    top_contributors,
    media_ratio,
    most_active_hour,
    most_active_day,
    most_used_words,
    date_range,
    compute_stats,
)


# ─── SAMPLE DATA ──────────────────────────────────────────────────────────────
# We build a small list of Message objects that covers all the cases
# we want to test: normal messages, media, system, multiple senders,
# multiple days, multiple hours.
# Using fixed timestamps means the test results are predictable and
# will never change based on when the tests are run.

SAMPLE_MESSAGES = [
    # Day 1 — Monday 18 Apr 2026, 10am
    Message(
        timestamp=datetime(2026, 4, 20, 10, 0),
        sender="Daniel",
        content="has anyone submitted the assignment",
        is_media=False,
        is_system=False
    ),
    # Day 1 — Monday 18 Apr 2026, 10am
    Message(
        timestamp=datetime(2026, 4, 20, 10, 5),
        sender="Eric",
        content="not yet working on it now",
        is_media=False,
        is_system=False
    ),
    # Day 1 — Monday 18 Apr 2026, 11am — media message
    Message(
        timestamp=datetime(2026, 4, 20, 11, 0),
        sender="Daniel",
        content="<Media omitted>",
        is_media=True,
        is_system=False
    ),
    # Day 2 — Tuesday 19 Apr 2026, 10am
    Message(
        timestamp=datetime(2026, 4, 21, 10, 0),
        sender="Obafemi",
        content="assignment deadline is today",
        is_media=False,
        is_system=False
    ),
    # Day 2 — Tuesday 19 Apr 2026, 10am — system message
    Message(
        timestamp=datetime(2026, 4, 21, 10, 30),
        sender="Obafemi",
        content="left",
        is_media=False,
        is_system=True
    ),
    # Day 3 — Wednesday 20 Apr 2026, 14pm
    Message(
        timestamp=datetime(2026, 4, 22, 14, 0),
        sender="Eric",
        content="the assignment submission link is not working",
        is_media=False,
        is_system=False
    ),
]


# ─── TEST 1: TOTAL MESSAGES ───────────────────────────────────────────────────
# The sample has 6 messages but 1 is a system message.
# total_messages() should return 5 (excluding system messages).

def test_total_messages():
    result = total_messages(SAMPLE_MESSAGES)
    assert result == 5, f"Expected 5, got {result}"
    print("[PASSED] Test 1: total_messages returns correct count")


# ─── TEST 2: UNIQUE MEMBERS ───────────────────────────────────────────────────
# The sample has Daniel, Eric, and Obafemi sending non-system messages.
# Even though Daniel and Eric send multiple messages, each counts as one member.

def test_unique_members():
    result = unique_members(SAMPLE_MESSAGES)
    assert result == 3, f"Expected 3, got {result}"
    print("[PASSED] Test 2: unique_members returns correct count")


# ─── TEST 3: ACTIVE DAYS ──────────────────────────────────────────────────────
# Messages span 3 distinct calendar days: Apr 18, Apr 19, Apr 20.
# The system message on Apr 19 is excluded but the day still counts
# because there are non-system messages on that day too.

def test_active_days():
    result = active_days(SAMPLE_MESSAGES)
    assert result == 3, f"Expected 3, got {result}"
    print("[PASSED] Test 3: active_days returns correct count")


# ─── TEST 4: TOP CONTRIBUTORS ─────────────────────────────────────────────────
# Non-system message counts: Daniel=2, Eric=2, Obafemi=1.
# The top contributor should be Daniel or Eric (both have 2).
# We just check that the top count is 2 and Obafemi has 1.

def test_top_contributors():
    result = top_contributors(SAMPLE_MESSAGES)
    # Result is a list of (sender, count) tuples
    counts = dict(result)
    assert counts["Daniel"] == 2, f"Expected Daniel to have 2, got {counts['Daniel']}"
    assert counts["Eric"] == 2, f"Expected Eric to have 2, got {counts['Eric']}"
    assert counts["Obafemi"] == 1, f"Expected Obafemi to have 1, got {counts['Obafemi']}"
    print("[PASSED] Test 4: top_contributors returns correct counts")


# ─── TEST 5: MEDIA RATIO ──────────────────────────────────────────────────────
# 5 non-system messages, 1 of which is media.
# media_count should be 1, text_count should be 4, media_percent should be 20.0

def test_media_ratio():
    result = media_ratio(SAMPLE_MESSAGES)
    assert result["media_count"] == 1, f"Expected 1 media, got {result['media_count']}"
    assert result["text_count"] == 4, f"Expected 4 text, got {result['text_count']}"
    assert result["media_percent"] == 20.0, f"Expected 20.0%, got {result['media_percent']}"
    print("[PASSED] Test 5: media_ratio returns correct breakdown")


# ─── TEST 6: MOST ACTIVE HOUR ─────────────────────────────────────────────────
# Hour 10 has 3 non-system messages (two on Apr 18 and one on Apr 19).
# Hour 11 has 1, hour 14 has 1.
# most_active_hour() should return 10.

def test_most_active_hour():
    result = most_active_hour(SAMPLE_MESSAGES)
    assert result == 10, f"Expected 10, got {result}"
    print("[PASSED] Test 6: most_active_hour returns correct hour")


# ─── TEST 7: MOST ACTIVE DAY ──────────────────────────────────────────────────
# Monday (Apr 18) has 3 non-system messages.
# Tuesday (Apr 19) has 1, Wednesday (Apr 20) has 1.
# most_active_day() should return "Monday".

def test_most_active_day():
    result = most_active_day(SAMPLE_MESSAGES)
    assert result == "Monday", f"Expected Monday, got {result}"
    print("[PASSED] Test 7: most_active_day returns correct day")


# ─── TEST 8: MOST USED WORDS ──────────────────────────────────────────────────
# The word "assignment" appears in 3 messages.
# It should appear in the top words list.
# Media and system messages should be excluded from word counts.

def test_most_used_words():
    result = most_used_words(SAMPLE_MESSAGES)
    words = [word for word, count in result]
    assert "assignment" in words, "Expected 'assignment' to be in top words"
    print("[PASSED] Test 8: most_used_words includes expected word")


# ─── TEST 9: DATE RANGE ───────────────────────────────────────────────────────
# Earliest message is Apr 18 2026, latest is Apr 20 2026.
# date_range() should return "18 Apr 2026 - 20 Apr 2026".

def test_date_range():
    result = date_range(SAMPLE_MESSAGES)
    assert result == "20 Apr 2026 - 22 Apr 2026", f"Expected '20 Apr 2026 - 22 Apr 2026', got {result}"
    print("[PASSED] Test 9: date_range returns correct range")


# ─── TEST 10: COMPUTE STATS ───────────────────────────────────────────────────
# compute_stats() is the main function the Flask app calls.
# It should return a dictionary with all the expected keys.

def test_compute_stats():
    result = compute_stats(SAMPLE_MESSAGES)
    expected_keys = [
        "total_messages", "unique_members", "active_days",
        "top_contributors", "media_ratio", "most_active_hour",
        "most_active_day", "hour_distribution", "most_used_words",
        "date_range",
    ]
    for key in expected_keys:
        assert key in result, f"Expected key '{key}' missing from compute_stats output"
    print("[PASSED] Test 10: compute_stats returns all expected keys")


# ─── RUN ALL TESTS ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Running stats tests...\n")
    test_total_messages()
    test_unique_members()
    test_active_days()
    test_top_contributors()
    test_media_ratio()
    test_most_active_hour()
    test_most_active_day()
    test_most_used_words()
    test_date_range()
    test_compute_stats()
    print("\nAll stats tests complete.")