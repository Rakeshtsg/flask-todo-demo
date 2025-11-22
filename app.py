import os
import json
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from pathlib import Path

# Load .env if present
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
# Needed for flash messages
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_this_in_production")

# Mongo settings via environment variables
MONGO_URI = os.environ.get("MONGO_URI")  # e.g. mongodb+srv://user:pass@cluster0.mongodb.net
DB_NAME = os.environ.get("DB_NAME", "mydatabase")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "submissions")

# Setup Mongo client lazily (so app can still serve /api without Mongo configured)
mongo_client = None
def get_mongo_collection():
    global mongo_client
    if MONGO_URI is None:
        raise RuntimeError("MONGO_URI is not configured in environment variables.")
    if mongo_client is None:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Optionally test connection here with mongo_client.server_info()
    db = mongo_client[DB_NAME]
    return db[COLLECTION_NAME]

# ---- Endpoint 1: /api reads backend file and returns JSON list ----
DATA_FILE = Path(__file__).parent / "data.json"

@app.route("/api", methods=["GET"])
def api_list():
    """
    Read the backend data.json file and return its content as JSON.
    File content must be a JSON list, e.g. [ {"id":1, "name":"A"}, ... ]
    """
    if not DATA_FILE.exists():
        # Return empty list if file missing
        return jsonify([])

    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure it's a list before returning
        if not isinstance(data, list):
            return jsonify({"error": "backend file does not contain a JSON list"}), 500
        return jsonify(data)
    except json.JSONDecodeError:
        return jsonify({"error": "invalid JSON in backend file"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---- Frontend: form and submission ----
@app.route("/", methods=["GET"])
def form():
    # Render form with optional flashed error message
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    # Expecting form fields: name, email, message (example). Add/adjust to suit.
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    # Basic validation
    if not name or not email:
        # Flash error and re-render form with previous input retained via template
        flash("Name and email are required.", "error")
        return render_template("form.html", name=name, email=email, message=message), 400

    # Build document to insert
    doc = {
        "name": name,
        "email": email,
        "message": message,
    }

    try:
        collection = get_mongo_collection()
        result = collection.insert_one(doc)
        # On success, redirect to success page
        return redirect(url_for("success"))
    except RuntimeError as re:
        # Missing MONGO_URI or similar configuration error
        flash(f"Server configuration error: {str(re)}", "error")
        return render_template("form.html", name=name, email=email, message=message), 500
    except PyMongoError as pe:
        # Database error: show message on same page (no redirect)
        flash(f"Database error: {str(pe)}", "error")
        return render_template("form.html", name=name, email=email, message=message), 500
    except Exception as e:
        # Generic
        flash(f"Unexpected error: {str(e)}", "error")
        return render_template("form.html", name=name, email=email, message=message), 500

@app.route("/success", methods=["GET"])
def success():
    return render_template("success.html")

if __name__ == "__main__":
    # Run dev server
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=debug)
