import re                      # Python's built-in regex library — used to match patterns in text
import zipfile                 # Built-in Python library for opening and extracting .zip files
import os                      # Built-in Python library for file and folder path operations
from dataclasses import dataclass  # Lets us create clean data objects with named fields without writing a full class
from datetime import datetime      # Used to convert raw timestamp strings into real Python datetime objects
from typing import Optional        # Allows a field to be either a value or None, without crashing


# ─── MESSAGE OBJECT ───────────────────────────────────────────────────────────
# This defines what a single parsed WhatsApp message looks like.
# Every message in the chat will be converted into one of these objects.
# @dataclass automatically generates __init__ and __repr__ so we don't have to write them manually.

@dataclass
class Message:
    timestamp: Optional[datetime]  # When the message was sent. Optional because some timestamps may not parse cleanly
    sender: str                    # The name or phone number of the person who sent the message
    content: str                   # The actual text of the message
    is_media: bool                 # True if the message is a media placeholder like "<Media omitted>"
    is_system: bool                # True if this is a system event like "John left" or "You were added"


# ─── DATE FORMAT VARIANTS ─────────────────────────────────────────────────────
# WhatsApp exports timestamps differently depending on the device, region, and settings.
# For example, an iPhone in Nigeria might export "12/05/2024, 10:30 AM"
# while an Android might export "12/05/2024, 10:30:45".
# We list every known format here so the parser can try them one by one
# until one works, instead of breaking on an unfamiliar format.

DATE_FORMATS = [
    "%d/%m/%Y, %I:%M:%S %p",   # e.g. 12/05/2024, 10:30:45 AM — day first, 12hr with seconds
    "%d/%m/%Y, %I:%M %p",      # e.g. 12/05/2024, 10:30 AM   — day first, 12hr without seconds
    "%d/%m/%Y, %H:%M:%S",      # e.g. 12/05/2024, 10:30:45   — day first, 24hr with seconds
    "%d/%m/%Y, %H:%M",         # e.g. 12/05/2024, 10:30       — day first, 24hr without seconds
    "%m/%d/%Y, %I:%M:%S %p",   # e.g. 05/12/2024, 10:30:45 AM — month first (US format), 12hr with seconds
    "%m/%d/%Y, %I:%M %p",      # e.g. 05/12/2024, 10:30 AM   — month first (US format), 12hr without seconds
]


# ─── MAIN REGEX PATTERN ───────────────────────────────────────────────────────
# This is the core of the parser. It reads a single line and tries to extract
# three things from it: the timestamp, the sender's name, and the message content.
#
# A typical WhatsApp export line looks like one of these:
#   [12/05/2024, 10:30 AM] John Doe: Have you seen the assignment?
#   12/05/2024, 10:30 AM - John Doe: Have you seen the assignment?
#
# Breaking the pattern down piece by piece:
#   [\[‎]?           — optionally matches an opening bracket [ or a hidden WhatsApp formatting character
#                      (the ‎ is a zero-width character WhatsApp sometimes inserts — invisible but real)
#   (               — opens the first capture group: the timestamp
#     \d{1,2}/\d{1,2}/\d{2,4}  — matches the date: 1-2 digits, slash, 1-2 digits, slash, 2-4 digits
#     ,\s            — matches the comma and space after the date
#     \d{1,2}:\d{2}  — matches the time: hours and minutes
#     (?::\d{2})?    — optionally matches seconds (:45) — the ?: means don't capture, just match
#     (?:\s?[AP]M)?  — optionally matches AM or PM with an optional space before it
#   )               — closes the timestamp capture group
#   [\]‎\s\-]+       — matches whatever separates the timestamp from the sender name
#                      (could be a closing bracket, a dash, a space, or any combination)
#   ([^:]+?)        — second capture group: the sender name
#                      [^:]+ means "one or more characters that are NOT a colon"
#                      the ? makes it non-greedy so it stops at the first colon it finds
#   :\s             — matches the colon and space that separates the sender from the message
#   (.+)            — third capture group: the message content — everything after the colon

MESSAGE_PATTERN = re.compile(
    r'[\[‎]?(\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)[\]‎\s\-]+([^:]+?):\s(.+)',
    re.MULTILINE   # Makes the pattern work correctly across a file with many lines
)


# ─── KEYWORD LISTS ────────────────────────────────────────────────────────────
# When a media file is shared on WhatsApp but you export without media,
# WhatsApp replaces the file with a placeholder text. These are all the
# placeholder variants we check for to flag a message as media.

MEDIA_KEYWORDS = [
    "<media omitted>",    # Most common placeholder
    "image omitted",      # Seen on some Android exports
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "document omitted",
]

# When someone joins, leaves, or changes a group setting, WhatsApp inserts
# a system message that looks like a regular message but has no real sender.
# These keywords help us identify and flag those lines.

SYSTEM_KEYWORDS = [
    "added",
    "removed",
    "left",
    "created group",
    "changed the subject",
    "changed this group",
    "messages and calls are end-to-end encrypted",
    "you were added",
    "joined using this group",
]


# ─── ZIP EXTRACTOR ────────────────────────────────────────────────────────────
# WhatsApp always exports chats as a .zip file containing the .txt and any media.
# This function opens the zip, finds the .txt file inside it, extracts it
# into the data/ folder, and returns the path to the extracted .txt file
# so parse_export can then read it normally.

def extract_whatsapp_zip(zip_path: str, extract_to: str = "data/") -> str:
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Loop through everything inside the zip
        for filename in zip_ref.namelist():
            # Find the .txt file — that's the chat export, ignore everything else
            if filename.endswith('.txt'):
                zip_ref.extract(filename, extract_to)      # Extract it to the data/ folder
                return os.path.join(extract_to, filename)  # Return the full path to it

    # If no .txt file was found inside the zip, raise an error
    raise ValueError("No .txt file found in the zip. Make sure this is a valid WhatsApp export.")


# ─── TIMESTAMP PARSER ─────────────────────────────────────────────────────────
# Takes the raw timestamp string extracted by the regex (e.g. "12/05/2024, 10:30 AM")
# and tries to convert it into a real Python datetime object.
# It loops through every format in DATE_FORMATS and tries each one.
# The moment a format works, it returns the result immediately.
# If none of the formats match, it returns None instead of crashing the whole parser.

def parse_timestamp(raw: str) -> Optional[datetime]:
    raw = raw.strip()                      # Remove any accidental whitespace around the string
    for fmt in DATE_FORMATS:               # Try each format one by one
        try:
            return datetime.strptime(raw, fmt)   # strptime converts a string to a datetime using a format
        except ValueError:                 # If this format doesn't match, Python raises ValueError
            continue                       # Ignore the error and try the next format
    return None                            # If nothing worked, return None


# ─── MEDIA DETECTOR ───────────────────────────────────────────────────────────
# Checks whether a message's content contains any of the media placeholder keywords.
# .lower() converts the content to lowercase first so the check is case-insensitive —
# "<Media Omitted>" and "<media omitted>" will both be caught.
# any() returns True as soon as it finds one match, without checking the rest.

def is_media_message(content: str) -> bool:
    return any(kw in content.lower() for kw in MEDIA_KEYWORDS)


# ─── SYSTEM MESSAGE DETECTOR ──────────────────────────────────────────────────
# Checks whether a line is a WhatsApp system event rather than a real message.
# We combine the sender and content into one string before checking because
# system messages sometimes split information across both fields depending on the export.
# For example, the sender might be "John" and the content "left" — combining them
# gives "john left" which matches the "left" keyword correctly.

def is_system_message(sender: str, content: str) -> bool:
    combined = (sender + " " + content).lower()    # Join sender and content, make lowercase
    return any(kw in combined for kw in SYSTEM_KEYWORDS)


# ─── MAIN PARSER FUNCTION ─────────────────────────────────────────────────────
# This is the function you actually call. You give it the path to a WhatsApp .txt file
# and it returns a list of clean Message objects — one for every message in the chat.

def parse_export(filepath: str) -> list[Message]:

    # Open the file with UTF-8 encoding to handle emojis and special characters correctly
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()    # Read every line into a list — each item is one line of the file

    messages = []     # This will hold all the finished Message objects
    current = None    # Tracks the message we're currently building

    for line in lines:
        line = line.strip()    # Remove leading/trailing whitespace and newline characters
        if not line:           # Skip completely empty lines
            continue

        # Try to match this line against the message pattern
        match = MESSAGE_PATTERN.match(line)

        if match:
            # ── This line is the START of a new message ──
            # The regex found a timestamp, sender, and content — this is a fresh message.

            if current:
                # Before starting the new message, save the one we were building.
                # This is how every message gets added to the list — when the NEXT one starts.
                messages.append(current)

            # Pull the three captured groups out of the regex match
            raw_time, sender, content = match.groups()

            # Build a new Message object with all five fields populated
            current = Message(
                timestamp=parse_timestamp(raw_time),         # Convert raw string to datetime
                sender=sender.strip(),                        # Clean up any extra whitespace around the name
                content=content.strip(),                      # Clean up the message content
                is_media=is_media_message(content),           # Check if it's a media placeholder
                is_system=is_system_message(sender, content)  # Check if it's a system event
            )

        elif current:
            # ── This line has no timestamp — it's a CONTINUATION of the previous message ──
            # WhatsApp messages can span multiple lines. If someone presses Enter mid-message,
            # the next line has no timestamp and no sender — it's just more content.
            # We append it to the current message's content with a newline to preserve formatting.
            current.content += "\n" + line

    # ── After the loop, save the very last message ──
    # The loop only saves a message when the NEXT one starts.
    # The final message in the file never triggers that save, so we do it manually here.
    if current:
        messages.append(current)

    return messages    # Return the complete list of structured Message objects
