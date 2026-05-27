# dashboard/stats.py
#
# This file is responsible for one thing: taking the list of Message objects
# that the parser returns and computing useful statistics from them.
#
# It has no UI, no Flask, no Azure. It is pure data computation.
# The Flask app in app.py will call these functions and pass the results
# to the browser for display.
#
# Every function here takes a list of Message objects as input and returns
# a plain Python value (a number, a list, a dictionary) as output.
# That makes each function easy to test independently.

from collections import Counter
from datetime import datetime
from parser.whatsapp_parser import Message


# ─── TOTAL MESSAGE COUNT ──────────────────────────────────────────────────────
# Returns the total number of messages in the chat, excluding system messages.
# System messages like "John left" or "You were added" are not real messages
# from participants, so we exclude them from all counts.

def total_messages(messages: list[Message]) -> int:
    return len([m for m in messages if not m.is_system])


# ─── UNIQUE MEMBERS ───────────────────────────────────────────────────────────
# Returns the number of unique senders in the chat.
# Again, system messages are excluded because they do not have real senders.
# Using a set automatically removes duplicates — if Daniel sent 500 messages,
# he still only counts as one unique member.

def unique_members(messages: list[Message]) -> int:
    senders = set(m.sender for m in messages if not m.is_system)
    return len(senders)


# ─── ACTIVE DAYS ──────────────────────────────────────────────────────────────
# Returns the number of distinct calendar days on which at least one message
# was sent. This gives a sense of how long the group has been active.
# We extract just the date part (no time) from each timestamp and put them
# in a set to remove duplicates, then count the set.
# Messages with no timestamp (where parsing failed) are skipped with the
# "if m.timestamp" check.

def active_days(messages: list[Message]) -> int:
    days = set(
        m.timestamp.date()
        for m in messages
        if not m.is_system and m.timestamp
    )
    return len(days)


# ─── TOP CONTRIBUTORS ─────────────────────────────────────────────────────────
# Returns the top N senders by message count as a list of (sender, count) tuples.
# Counter is a built-in Python class that counts occurrences of items in a list.
# .most_common(n) returns the n most frequent items in descending order.
# Default is top 5, but the caller can pass a different number.

def top_contributors(messages: list[Message], n: int = 5) -> list[tuple]:
    senders = [m.sender for m in messages if not m.is_system]
    return Counter(senders).most_common(n)


# ─── MEDIA VS TEXT RATIO ──────────────────────────────────────────────────────
# Returns a dictionary with three values:
#   - media_count: number of media messages
#   - text_count: number of text messages
#   - media_percent: what percentage of all messages are media
# This is useful for understanding the nature of the group —
# some groups are mostly file sharing, others are mostly conversation.

def media_ratio(messages: list[Message]) -> dict:
    non_system = [m for m in messages if not m.is_system]
    media = [m for m in non_system if m.is_media]
    text = [m for m in non_system if not m.is_media]

    total = len(non_system)

    # Avoid division by zero if the chat is somehow empty
    percent = round(len(media) / total * 100, 1) if total > 0 else 0

    return {
        "media_count": len(media),
        "text_count": len(text),
        "media_percent": percent,
    }


# ─── MOST ACTIVE HOUR ─────────────────────────────────────────────────────────
# Returns the hour of the day (0-23) during which the most messages were sent.
# This tells you when the group is most active — useful context for a student
# group (e.g. most messages sent at 11pm before a deadline).
# Messages with no timestamp are skipped.

def most_active_hour(messages: list[Message]) -> int:
    hours = [
        m.timestamp.hour
        for m in messages
        if not m.is_system and m.timestamp
    ]

    if not hours:
        return None

    # Counter counts how many messages were sent in each hour,
    # most_common(1) returns the single most frequent hour as a list of one tuple,
    # [0][0] extracts just the hour number from that tuple
    return Counter(hours).most_common(1)[0][0]


# ─── MOST ACTIVE DAY OF THE WEEK ──────────────────────────────────────────────
# Returns the name of the weekday (e.g. "Monday") on which the most messages
# were sent across the entire history of the chat.
# strftime("%A") converts a date to its full weekday name.

def most_active_day(messages: list[Message]) -> str:
    days = [
        m.timestamp.strftime("%A")
        for m in messages
        if not m.is_system and m.timestamp
    ]

    if not days:
        return None

    return Counter(days).most_common(1)[0][0]


# ─── HOUR DISTRIBUTION ────────────────────────────────────────────────────────
# Returns a dictionary mapping each hour (0-23) to the number of messages
# sent during that hour. This is used to draw the activity chart on the
# dashboard — a bar for each hour of the day showing message volume.
# Hours with no messages will simply not appear in the dictionary.

def hour_distribution(messages: list[Message]) -> dict:
    hours = [
        m.timestamp.hour
        for m in messages
        if not m.is_system and m.timestamp
    ]
    return dict(Counter(hours))


# ─── DATE RANGE ───────────────────────────────────────────────────────────────
# Returns a human-readable string showing the date range of the chat.
# For example: "17 Apr 2026 - 24 May 2026"
# This gives the user immediate context about what period they are looking at.
# We find the earliest and latest timestamps in the message list,
# then format them as readable date strings.

def date_range(messages: list[Message]) -> str:
    timestamps = [
        m.timestamp for m in messages
        if not m.is_system and m.timestamp
    ]

    if not timestamps:
        return None

    earliest = min(timestamps)
    latest = max(timestamps)

    # strftime formats a datetime into a readable string.
    # "%d %b %Y" produces e.g. "17 Apr 2026"
    return f"{earliest.strftime('%d %b %Y')} - {latest.strftime('%d %b %Y')}"


# ─── MOST USED WORDS ──────────────────────────────────────────────────────────
# Returns the top N most frequently used words across all text messages.
# We strip out stopwords — extremely common words like "the", "a", "is",
# "you", "i" — because they appear in almost every message and tell us
# nothing meaningful about what the group actually talks about.
# We also skip media messages, system messages, and very short words
# (under 3 characters) to keep the results meaningful.
# The result is a list of (word, count) tuples sorted by frequency.

def most_used_words(messages: list[Message], n: int = 10) -> list[tuple]:
    # Common English and Nigerian Pidgin filler words to ignore
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "is", "it", "this", "that", "was", "are",
        "be", "as", "by", "from", "have", "has", "had", "not", "we",
        "you", "i", "he", "she", "they", "my", "your", "our", "his",
        "her", "its", "me", "him", "us", "them", "do", "did", "will",
        "can", "just", "so", "if", "up", "out", "about", "what", "how",
        "when", "who", "all", "been", "would", "could", "should", "than",
        "then", "there", "their", "more", "also", "into", "no", "yes",
        "ok", "okay", "na", "de", "go", "am", "im", "ur", "u", "r",
        "abi", "sha", "sef", "oo", "oh", "ah", "hm", "lol", "now",
    }

    words = []

    for m in messages:
        # Skip media and system messages — they have no real text content
        if m.is_media or m.is_system:
            continue

        # Convert to lowercase and split into individual words.
        # We remove punctuation by keeping only alphanumeric characters.
        for word in m.content.lower().split():
            # Strip punctuation from start and end of word
            clean = ''.join(c for c in word if c.isalnum())

            # Skip empty strings, stopwords, and very short words
            if clean and len(clean) >= 3 and clean not in stopwords:
                words.append(clean)

    return Counter(words).most_common(n)


# ─── FULL STATS SUMMARY ───────────────────────────────────────────────────────
# This is the main function the Flask app will call.
# It runs all the individual stat functions above and bundles their results
# into a single dictionary that can be passed directly to the HTML template.
# Having one function that returns everything means the Flask route only
# needs to make one call instead of six.

def compute_stats(messages: list[Message]) -> dict:
    return {
        "total_messages": total_messages(messages),
        "unique_members": unique_members(messages),
        "active_days": active_days(messages),
        "top_contributors": top_contributors(messages),
        "media_ratio": media_ratio(messages),
        "most_active_hour": most_active_hour(messages),
        "most_active_day": most_active_day(messages),
        "hour_distribution": hour_distribution(messages),
        "date_range": date_range(messages),
        "most_used_words": most_used_words(messages),
    }