# app.py
#
# The main Flask web application.
# Handles all routes: the upload page, the dashboard, and the filter results.
#
# Routes:
#   GET  /              — upload page
#   POST /              — process uploaded file, show dashboard
#   GET  /filter/<name> — show filtered messages for a given filter category

import os
from flask import Flask, render_template, request, redirect, url_for
from parser.whatsapp_parser import parse_export, extract_whatsapp_zip
from dashboard.stats import compute_stats
from ai.entity_extractor import extract_entities, entity_summary
from ai.key_phrase_extractor import extract_key_phrases
from parser.filters import apply_filter

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "whatsapp-extractor-dev-key")

UPLOAD_FOLDER = "data"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Module-level variable that stores parsed messages between requests.
# Set when a file is uploaded, read when filters are applied.
# Resets every time Flask restarts.
_messages_store = []


# ─── ROUTE 1: UPLOAD PAGE ─────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


# ─── ROUTE 2: PROCESS UPLOAD AND SHOW DASHBOARD ───────────────────────────────
@app.route("/", methods=["POST"])
def upload():
    global _messages_store

    if "file" not in request.files:
        return redirect(url_for("index"))

    file = request.files["file"]

    if file.filename == "":
        return redirect(url_for("index"))

    if not file.filename.endswith(".zip"):
        return render_template("index.html", error="Please upload a WhatsApp .zip export file.")

    # Save the uploaded file
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    # Step 1: Extract the .txt from the zip
    txt_path = extract_whatsapp_zip(filepath)

    # Step 2: Parse the .txt into Message objects
    messages = parse_export(txt_path)

    # Step 3: Run entity extraction — attaches entities field to each message
    messages = extract_entities(messages)

    # Step 4: Run key phrase extraction — attaches key_phrases field to each message
    messages = extract_key_phrases(messages)

    # Step 5: Store messages in memory for filter routes to use
    _messages_store = messages

    # Step 6: Compute dashboard statistics
    stats = compute_stats(messages)
    e_summary = entity_summary(messages)

    return render_template("dashboard.html", stats=stats, entity_summary=e_summary)


# ─── ROUTE 3: FILTER RESULTS ──────────────────────────────────────────────────
# Handles all five preset filters via a single route.
# The filter name comes from the URL — /filter/links, /filter/deadlines, etc.

@app.route("/filter/<filter_name>")
def filter_results(filter_name):
    global _messages_store

    if not _messages_store:
        return redirect(url_for("index"))

    results = apply_filter(filter_name, _messages_store)

    filter_labels = {
        "links": "Links",
        "deadlines": "Deadlines",
        "announcements": "Announcements",
        "questions": "Questions",
        "media": "Files & Media",
    }

    label = filter_labels.get(filter_name, filter_name.capitalize())

    return render_template(
        "results.html",
        messages=results,
        filter_name=label,
        total=len(results),
        source="filter"
    )


# ─── RUN THE APP ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)