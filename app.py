# app.py
#
# This is the entry point of the web application.
# It creates the Flask app, defines the two routes (pages), and connects
# everything together: the file upload, the parser, the stats computation,
# and the HTML templates.
#
# Route 1: GET /  — shows the upload page
# Route 2: POST / — receives the uploaded file, parses it, computes stats,
#                   and renders the dashboard

import os
from flask import Flask, render_template, request, redirect, url_for
from parser.whatsapp_parser import parse_export, extract_whatsapp_zip
from dashboard.stats import compute_stats

# Create the Flask application instance.
# __name__ tells Flask where to look for templates and static files —
# it uses the location of this file as the reference point.
app = Flask(__name__)

# The folder where uploaded files will be temporarily saved.
# We use the data/ folder which is already gitignored, so uploads
# never accidentally get committed to GitHub.
UPLOAD_FOLDER = "data"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ─── ROUTE 1: UPLOAD PAGE ─────────────────────────────────────────────────────
# This route handles GET requests to the root URL (/).
# A GET request is what happens when someone opens a URL in their browser
# without submitting a form. It simply renders the upload page.

@app.route("/", methods=["GET"])
def index():
    # render_template looks for index.html inside the templates/ folder
    # and returns it as an HTML response to the browser
    return render_template("index.html")


# ─── ROUTE 2: HANDLE UPLOAD AND SHOW DASHBOARD ────────────────────────────────
# This route handles POST requests to the root URL (/).
# A POST request is what happens when a user submits the upload form.
# Flask receives the uploaded file, saves it, parses it, computes stats,
# and renders the dashboard with the results.

@app.route("/", methods=["POST"])
def upload():
    # Check if a file was actually included in the request.
    # If the user clicked upload without selecting a file, redirect back
    # to the upload page rather than crashing.
    if "file" not in request.files:
        return redirect(url_for("index"))

    file = request.files["file"]

    # If the user submitted the form with no file selected,
    # the filename will be an empty string. Handle that gracefully.
    if file.filename == "":
        return redirect(url_for("index"))

    # Check that the uploaded file is a zip file.
    # We only accept zip files because that is what WhatsApp exports.
    if not file.filename.endswith(".zip"):
        return render_template("index.html", error="Please upload a WhatsApp .zip export file.")

    # Save the uploaded file to the data/ folder
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    # Extract the .txt file from the zip using our parser's zip extractor.
    # This gives us the path to the extracted .txt file.
    txt_path = extract_whatsapp_zip(filepath)

    # Parse the extracted .txt file into a list of Message objects
    messages = parse_export(txt_path)

    # Compute all statistics from the parsed messages
    stats = compute_stats(messages)

    # Render the dashboard template, passing the stats dictionary to it.
    # The template can access any key from the stats dict directly by name.
    return render_template("dashboard.html", stats=stats)


# ─── RUN THE APP ──────────────────────────────────────────────────────────────
# This block only runs when you execute app.py directly with Python.
# debug=True means Flask will automatically reload when you save changes
# to any file, and will show detailed error messages in the browser
# instead of a generic 500 error. Never use debug=True in production.

if __name__ == "__main__":
    app.run(debug=True)