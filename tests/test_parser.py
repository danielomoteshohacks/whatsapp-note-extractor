import sys
import os

# This tells Python where to find the parser module — without this line,
# the test file wouldn't know where whatsapp_parser.py lives
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from parser.whatsapp_parser import parse_export, extract_whatsapp_zip, Message


# ─── TEST 1: NORMAL MESSAGE ───────────────────────────────────────────────────
# Creates a temporary .txt file with one normal message and checks that
# the parser correctly extracts the sender, content, and flags

def test_normal_message():
    # Write a sample export line to a temporary file
    sample = "18/04/2026, 19:49 - Felix: Hello bro\n"
    with open("tests/temp_test.txt", "w", encoding="utf-8") as f:
        f.write(sample)

    messages = parse_export("tests/temp_test.txt")

    assert len(messages) == 1, "Should have parsed exactly 1 message"
    assert messages[0].sender == "Felix", "Sender should be Felix"
    assert messages[0].content == "Hello bro", "Content should be 'Hello bro'"
    assert messages[0].is_media == False, "Should not be flagged as media"
    assert messages[0].is_system == False, "Should not be flagged as system"
    print("[PASSED] Test 1: Normal message parsed correctly")


# ─── TEST 2: MEDIA MESSAGE ────────────────────────────────────────────────────
# Checks that a message with <Media omitted> is correctly flagged as media

def test_media_message():
    sample = "24/04/2026, 19:22 - Felix: <Media omitted>\n"
    with open("tests/temp_test.txt", "w", encoding="utf-8") as f:
        f.write(sample)

    messages = parse_export("tests/temp_test.txt")

    assert len(messages) == 1, "Should have parsed exactly 1 message"
    assert messages[0].is_media == True, "Should be flagged as media"
    assert messages[0].is_system == False, "Should not be flagged as system"
    print("[PASSED] Test 2: Media message flagged correctly")


# ─── TEST 3: SYSTEM MESSAGE ───────────────────────────────────────────────────
# Checks that a WhatsApp system event is correctly flagged as a system message

def test_system_message():
    sample = "17/04/2026, 17:36 - Daniel: Messages and calls are end-to-end encrypted. Only people in this chat can read them.\n"
    with open("tests/temp_test.txt", "w", encoding="utf-8") as f:
        f.write(sample)

    messages = parse_export("tests/temp_test.txt")

    assert len(messages) == 1, "Should have parsed exactly 1 message"
    assert messages[0].is_system == True, "Should be flagged as system message"
    print("[PASSED] Test 3: System message flagged correctly")


# ─── TEST 4: MULTILINE MESSAGE ────────────────────────────────────────────────
# Checks that a message split across multiple lines is joined into one message.
# WhatsApp allows users to press Enter mid-message, which creates continuation
# lines in the export that have no timestamp or sender — they belong to the
# previous message and must be joined to it.

def test_multiline_message():
    sample = (
        "18/04/2026, 19:49 - Felix: Good evening\n"
        "How are you doing today?\n"
    )
    with open("tests/temp_test.txt", "w", encoding="utf-8") as f:
        f.write(sample)

    messages = parse_export("tests/temp_test.txt")

    assert len(messages) == 1, "Multiline message should be joined into 1 message"
    assert "How are you doing today?" in messages[0].content, "Second line should be part of the message content"
    print("[PASSED] Test 4: Multiline message joined correctly")


# ─── TEST 5: REAL EXPORT FILE ─────────────────────────────────────────────────
# This is the most important test — it runs the parser on a real WhatsApp export.
# First it calls extract_whatsapp_zip() to unzip the export from the data/ folder,
# which gives us the path to the extracted .txt file.
# Then it runs parse_export() on that .txt file and prints a summary so we can
# visually confirm the results look correct — total messages, media count,
# system message count, and a preview of the first 3 messages.

def test_real_export():
    # Automatically find the first zip file in the data/ folder
    # This avoids hardcoding the filename which can cause path issues on Windows
    zip_files = [f for f in os.listdir('data') if f.endswith('.zip')]
    if not zip_files:
        print("[SKIPPED] Test 5 skipped: No zip file found in data/ folder")
        return
    zip_path = os.path.join('data', zip_files[0])

    # Extract the .txt from the zip and get its path
    filepath = extract_whatsapp_zip(zip_path)

    # Run the parser on the extracted .txt file
    messages = parse_export(filepath)

    print(f"\n[PASSED] Test 5: Real export parsed successfully")
    print(f"   Total messages  : {len(messages)}")
    print(f"   Media messages  : {sum(1 for m in messages if m.is_media)}")
    print(f"   System messages : {sum(1 for m in messages if m.is_system)}")
    print(f"\n   First 3 messages:")
    for m in messages[:3]:
        print(f"   [{m.timestamp}] {m.sender}: {m.content[:60]}")


# ─── RUN ALL TESTS ────────────────────────────────────────────────────────────
# This block only runs when you execute this file directly with Python.
# It calls each test function one by one and cleans up the temp file at the end.

if __name__ == "__main__":
    print("Running parser tests...\n")
    test_normal_message()
    test_media_message()
    test_system_message()
    test_multiline_message()
    test_real_export()

    # Clean up the temporary file created during tests 1-4
    if os.path.exists("tests/temp_test.txt"):
        os.remove("tests/temp_test.txt")

    print("\nAll tests complete.")