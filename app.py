"""
Sheet Music Transposer – Flask application entry point.

Routes
------
GET  /                  – Web UI
POST /api/transpose     – Accept image + source/dest keys; return JSON with
                          original and transposed ABC notation.
"""

import logging
import os

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

from copilot_client import extract_abc_from_image
from transposer import MUSICAL_KEYS, transpose_abc

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# Maximum upload size: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    return render_template("index.html", keys=MUSICAL_KEYS)


@app.post("/api/transpose")
def api_transpose():
    # --- Validate input ---
    if "image" not in request.files:
        return jsonify({"error": "No image file provided."}), 400

    image_file = request.files["image"]

    if image_file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    mime_type = image_file.mimetype or "image/png"
    if mime_type not in ALLOWED_MIME_TYPES:
        return jsonify({"error": f"Unsupported image type: {mime_type}"}), 415

    source_key = request.form.get("source_key", "").strip()
    dest_key = request.form.get("dest_key", "").strip()

    if source_key not in MUSICAL_KEYS:
        return jsonify({"error": f"Unknown source key: {source_key!r}"}), 400
    if dest_key not in MUSICAL_KEYS:
        return jsonify({"error": f"Unknown destination key: {dest_key!r}"}), 400

    # --- Read image bytes ---
    image_bytes = image_file.read()

    # --- Step 1: Extract ABC notation via Copilot API ---
    try:
        original_abc = extract_abc_from_image(image_bytes, mime_type, source_key)
    except Exception as exc:
        logger.error("Image analysis failed: %s", exc, exc_info=True)
        return jsonify({"error": "Failed to analyse image. Check your GITHUB_TOKEN and try again."}), 502

    # --- Step 2: Transpose ---
    try:
        transposed_abc = transpose_abc(original_abc, source_key, dest_key)
    except Exception as exc:
        logger.error("Transposition failed: %s", exc, exc_info=True)
        return jsonify({"error": "Failed to transpose the score. Please try again."}), 500

    return jsonify(
        {
            "source_key": source_key,
            "dest_key": dest_key,
            "original_abc": original_abc,
            "transposed_abc": transposed_abc,
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
