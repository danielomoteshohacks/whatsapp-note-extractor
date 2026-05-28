# parser/filters.py
#
# This file contains the logic for all five preset filter categories.
# Each filter function takes a list of Message objects and returns only
# the messages that match that filter's criteria.
#
# The filters use two sources of data:
# 1. The entities field attached by the entity extractor on Day 4
#    (dates, URLs, phone numbers, persons, etc.)
# 2. The key_phrases field attached by the key phrase extractor on Day 5
#    (main topics and concepts in each message)
# 3. Simple pattern matching on the message content itself
#
# Every filter function follows the same signature:
#   def filter_name(messages: list[Message]) -> list[Message]
# This makes them easy to call uniformly from the Flask routes.

import re
from parser.whatsapp_parser import Message


# ─── HELPER: GET ENTITY CATEGORIES ───────────────────────────────────────────
# Returns a set of entity category names found in a message.
# For example: {"DateTime", "URL", "PhoneNumber"}
# Used by multiple filters to check what types of entities are present.

def get_entity_categories(message: Message) -> set:
    return {e.category for e in getattr(message, 'entities', [])}


# ─── FILTER 1: LINKS ──────────────────────────────────────────────────────────
# Returns messages that contain URLs.
# We check two things:
# 1. Whether Azure AI Language detected a URL entity in the message
# 2. Whether the content contains common URL patterns (http, www, .com, .ng)
#    as a fallback for URLs Azure might have missed
# A message matches if either check is true.

def filter_links(messages: list[Message]) -> list[Message]:
    # URL patterns to check in raw content
    url_pattern = re.compile(
        r'(https?://|www\.|\.com|\.ng|\.org|\.edu|\.io)',
        re.IGNORECASE
    )

    results = []
    for m in messages:
        if m.is_system:
            continue

        has_url_entity = "URL" in get_entity_categories(m)
        has_url_pattern = bool(url_pattern.search(m.content))

        if has_url_entity or has_url_pattern:
            results.append(m)

    return results


# ─── FILTER 2: DEADLINES ──────────────────────────────────────────────────────
# Returns messages that contain deadline-related information.
# A message is flagged as a deadline if it has a DateTime entity AND
# contains at least one deadline keyword in its content or key phrases.
# This two-part check reduces false positives — a message saying
# "good morning" should not be flagged even if Azure detects "morning"
# as a DateTime.

DEADLINE_KEYWORDS = [
    # Standard English — direct deadline language
    "submit", "submission", "deadline", "due", "due date",
    "before", "by tonight", "by tomorrow", "by today", "by monday",
    "by tuesday", "by wednesday", "by thursday", "by friday",
    "by saturday", "by sunday", "by end of", "by midnight",
    "urgent", "reminder", "last chance", "final reminder",
    "closes", "closing", "close today", "close tomorrow",
    "end of day", "eod", "midnight", "noon", "12pm", "12am",
    "no later than", "not later than", "final", "last date",
    "cut off", "cutoff", "time limit", "expire", "expiry",
    "hand in", "hand over", "turn in", "upload", "send in",
    "send it", "drop it", "drop the", "submit before",
    "registration closes", "registration deadline",
    "portal closes", "portal deadline",
    "exam registration", "course registration",
    "clearance deadline", "clearance closes",
    "payment deadline", "fee deadline", "school fees due",
    "assignment due", "project due", "report due",
    "today is the last", "last day", "last opportunity",
    "time is running out", "running out of time",
    "few hours left", "hours left", "minutes left",
    # Academic specific
    "tma", "tma deadline", "tma submission",
    "e-exam", "exam date", "exam time", "exam venue",
    "test date", "quiz date", "presentation date",
    "defence date", "seminar date", "lab date",
    # Nigerian Pidgin and expressions
    "abeg", "pls", "plss", "pleasee", "biko",
    "make sure", "ensure", "compulsory", "mandatory",
    "sharp sharp", "quick quick", "now now", "asap",
    "do am", "do quick", "do am fast", "do it fast",
    "before the time", "time don reach", "e don do",
    "no delay", "no waste time", "before e close",
    "before dem close", "last minute", "e go close",
    "time dey go", "e dey urgent", "e don remain small",
    "no dull yourself", "no slack", "no fall hand",
    "e important", "e very important", "very important",
    "take note", "note this", "please note",
]

def filter_deadlines(messages: list[Message]) -> list[Message]:
    results = []
    for m in messages:
        if m.is_system or m.is_media:
            continue

        has_datetime = "DateTime" in get_entity_categories(m)
        if not has_datetime:
            continue

        # Check if the message content contains any deadline keyword
        content_lower = m.content.lower()
        has_deadline_keyword = any(kw in content_lower for kw in DEADLINE_KEYWORDS)

        # Also check key phrases for deadline keywords
        phrases_lower = " ".join(getattr(m, 'key_phrases', [])).lower()
        has_deadline_phrase = any(kw in phrases_lower for kw in DEADLINE_KEYWORDS)

        if has_deadline_keyword or has_deadline_phrase:
            results.append(m)

    return results


# ─── FILTER 3: ANNOUNCEMENTS ──────────────────────────────────────────────────
# Returns messages that look like announcements.
# We identify announcements using two signals:
# 1. The message starts with an announcement pattern (attention, notice, reminder, etc.)
# 2. The message is longer than 100 characters and contains announcement keywords
# We deliberately avoid trying to detect "admin" messages by name because
# WhatsApp exports do not reliably mark admins — we use content signals instead.

ANNOUNCEMENT_STARTERS = [
    # Formal English starters
    "attention", "notice", "reminder", "announcement",
    "please note", "important", "update", "kindly",
    "dear all", "hi all", "hello all", "hello everyone",
    "good morning", "good afternoon", "good evening",
    "good day", "greetings",
    "to all", "for all", "note that", "be informed",
    "this is to inform", "this is to notify",
    "this is to remind", "this is to announce",
    "just a reminder", "quick reminder", "friendly reminder",
    "please be advised", "please be aware",
    "please be informed", "please be notified",
    "management has", "admin has", "the department",
    "the faculty", "the school", "the university",
    "the course rep", "the cr", "class rep",
    "the lecturer", "the professor", "the hod",
    "on behalf of", "by the authority",
    # Nigerian university specific
    "guys", "people", "una", "make una", "abeg make",
    "make everyone", "everybody", "everyone in this group",
    "all members", "house", "the house",
    "bros and sis", "brothers and sisters",
    "fam", "family", "people in this group",
    "those who", "anyone who", "whoever",
    "course rep here", "cr here", "admin here",
    "class rep here", "your cr", "your course rep",
    "pls take note", "please take note",
    "for your information", "fyi",
    "just to let you know", "just to inform",
    "just to remind", "just a heads up",
    "heads up", "update for everyone",
    "general announcement", "important announcement",
    "urgent announcement", "emergency",
]

ANNOUNCEMENT_KEYWORDS = [
    # Standard English
    "please", "kindly", "note that", "be informed",
    "take note", "compulsory", "mandatory", "required",
    "must", "ensure", "inform", "notify", "advised",
    "directed", "instructed", "postponed", "rescheduled",
    "cancelled", "moved", "shifted", "change of",
    "change in", "new date", "new time", "new venue",
    "venue", "time", "date", "schedule", "timetable",
    "exam", "test", "quiz", "assignment", "project",
    "seminar", "lecture", "class", "lab", "practical",
    "course", "portal", "registration", "clearance",
    "result", "score", "grade", "gpa", "cgpa",
    "scholarship", "bursary", "fellowship", "award",
    "convocation", "graduation", "matriculation",
    "orientation", "induction", "resumption",
    "semester", "session", "academic calendar",
    "strike", "asuu", "suspension", "resumption",
    "hostel", "accommodation", "hall of residence",
    "school fees", "tuition", "payment", "invoice",
    "receipt", "clearance", "id card", "student id",
    "library", "library fine", "library card",
    "sport", "game", "competition", "event",
    "meeting", "general meeting", "agm",
    "election", "vote", "voting",
    # Nigerian pidgin expressions
    "abeg", "make una", "una should", "do am",
    "e don change", "e don shift", "dem say",
    "oga say", "lecturer say", "prof say",
    "hod say", "department say", "school say",
    "dem don announce", "dem don release",
    "result don drop", "result out",
    "timetable don drop", "timetable out",
    "list don drop", "list out",
    "form don open", "form don close",
    "portal don open", "portal don close",
    "e don shift", "e don change",
    "e don cancel", "dem cancel am",
    "no go", "no show", "no come",
    "make una come", "make una go",
    "make una submit", "make una register",
    "make una check", "make una see",
]

def filter_announcements(messages: list[Message]) -> list[Message]:
    results = []
    for m in messages:
        if m.is_system or m.is_media:
            continue

        content_lower = m.content.lower().strip()

        # Check if message starts with an announcement pattern
        starts_with_announcement = any(
            content_lower.startswith(starter)
            for starter in ANNOUNCEMENT_STARTERS
        )

        # Check if longer message contains announcement keywords
        has_announcement_keyword = (
            len(m.content) > 100 and
            any(kw in content_lower for kw in ANNOUNCEMENT_KEYWORDS)
        )

        if starts_with_announcement or has_announcement_keyword:
            results.append(m)

    return results


# ─── FILTER 4: QUESTIONS ──────────────────────────────────────────────────────
# Returns messages that are asking questions.
# We check three signals:
# 1. The message ends with a question mark
# 2. The message starts with a question word (who, what, when, where, why, how)
# 3. The message contains common Nigerian question phrases

QUESTION_STARTERS = [
    # Standard English question words
    "who", "what", "when", "where", "why", "how",
    "which", "whose", "whom",
    "is there", "are there", "does anyone", "do anyone",
    "has anyone", "can someone", "could someone",
    "would anyone", "will anyone",
    "please who", "please what", "please when",
    "please where", "please how", "please which",
    "anyone know", "does anyone know", "did anyone",
    "has the", "have the", "is the", "are the",
    "will the", "was the", "were the",
    "is it", "are we", "do we", "did we",
    "have we", "will we", "can we", "should we",
    "is this", "are these", "is that",
    "what is", "what are", "what was", "what were",
    "what time", "what date", "what day",
    "what venue", "what location", "what place",
    "when is", "when are", "when will", "when was",
    "where is", "where are", "where will", "where was",
    "who is", "who are", "who will", "who was",
    "how do", "how does", "how did", "how will",
    "how many", "how much", "how long", "how far",
    "why is", "why are", "why did", "why would",
    "which one", "which course", "which venue",
    "quick question", "i have a question",
    "someone help", "need help", "help me",
    "anyone help", "can anyone",
    # Nigerian Pidgin question starters
    "abeg who", "abeg wetin", "abeg where",
    "abeg when", "abeg how", "abeg which",
    "wetin", "wetin be", "wetin dey", "wetin happen",
    "wetin dey happen", "wetin be the",
    "wey", "wey be", "wey dey",
    "who get", "who get the", "who know", "who sabi",
    "una know", "anybody know", "anybody sabi",
    "who get answer", "who fit help",
    "e don", "dem don", "when dem", "how dem",
    "na who", "na wetin", "na when", "na where",
    "na how", "na which", "na why",
    "person wey", "person wey get", "person wey know",
    "make i ask", "i wan ask", "let me ask",
    "pls who", "pls what", "pls when",
    "pls where", "pls how",
    "no be", "shey", "shebi", "abi",
    "shey na", "shebi na", "abi na",
    "shey true", "shebi true", "abi true",
    "shey e be like", "no be so", "e be like",
    "i no understand", "i no sabi", "i dey confused",
    "somebody help", "help abeg", "abeg help",
    "una fit", "anyone fit", "who fit",
    "make we know", "let us know", "let me know",
    "shey anybody", "abi anybody", "shebi anybody",
    "shey there is", "abi there is",
    "any update", "any news", "any info",
    "any information", "any gist", "any latest",
    "what is the update", "what is the latest",
    "update please", "info please", "details please",
    # Unilag/Lagos specific
    "portal don open", "when portal go open",
    "when result go drop", "result don drop",
    "when timetable go come", "timetable don come",
    "form don close", "when form go close",
    "venue don change", "when e go change",
]

def filter_questions(messages: list[Message]) -> list[Message]:
    results = []
    for m in messages:
        if m.is_system or m.is_media:
            continue

        content_lower = m.content.lower().strip()

        # Check if message ends with a question mark
        ends_with_question = m.content.strip().endswith("?")

        # Check if message starts with a question word
        starts_with_question = any(
            content_lower.startswith(starter)
            for starter in QUESTION_STARTERS
        )

        if ends_with_question or starts_with_question:
            results.append(m)

    return results


# ─── FILTER 5: FILES AND MEDIA ────────────────────────────────────────────────
# Returns messages that contain shared files or media.
# This uses the is_media flag set by the parser on Day 2 —
# any message where WhatsApp replaced the content with a placeholder
# like "<Media omitted>" is included here.

def filter_media(messages: list[Message]) -> list[Message]:
    return [m for m in messages if m.is_media and not m.is_system]


# ─── FILTER REGISTRY ──────────────────────────────────────────────────────────
# A dictionary mapping filter names to their functions.
# The Flask route uses this to look up the right filter function
# based on the filter name passed in the URL.
# Adding a new filter in the future just means adding one line here.

FILTERS = {
    "links": filter_links,
    "deadlines": filter_deadlines,
    "announcements": filter_announcements,
    "questions": filter_questions,
    "media": filter_media,
}


def apply_filter(filter_name: str, messages: list[Message]) -> list[Message]:
    filter_fn = FILTERS.get(filter_name.lower())
    if not filter_fn:
        return []
    return filter_fn(messages)