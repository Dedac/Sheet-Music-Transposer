# Sheet Music Transposer

A locally running web application that uses the **GitHub Copilot API** to
analyse images of sheet music and transpose them to any musical key you choose.

## Features

- **Upload** a photo or scan of any sheet music (PNG, JPEG, GIF, WebP).
- **Select** a source key (the key the music is currently written in) and a
  destination key (the key you want to transpose to).
- **Transpose** — the image is sent to the GitHub Copilot / GitHub Models API
  which reads the notes using a vision model and returns them as ABC notation.
- **Render** — both the original and transposed scores are rendered
  side-by-side in the browser using [abcjs](https://www.abcjs.net/).
- **Download** the transposed score as a PNG image.

---

## Requirements

| Prerequisite | Version |
|---|---|
| Python | ≥ 3.10 |
| pip | any recent |
| GitHub personal access token | with `models:read` scope **or** Copilot access |

---

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/Dedac/Sheet-Music-Transposer.git
cd Sheet-Music-Transposer

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set your GITHUB_TOKEN
```

### Getting a GitHub Token

1. Go to <https://github.com/settings/tokens> (classic tokens) or fine-grained tokens.
2. Create a token and tick the **`models:read`** scope
   (required for the GitHub Models API).
3. Paste the token as `GITHUB_TOKEN` in your `.env` file.

---

## Running the App

```bash
python app.py
```

Then open <http://localhost:5000> in your browser.

---

## Project Structure

```
Sheet-Music-Transposer/
├── app.py              # Flask web application & API routes
├── copilot_client.py   # GitHub Copilot / Models API client (image → ABC)
├── transposer.py       # music21-based transposition logic
├── templates/
│   └── index.html      # Web UI
├── static/
│   ├── css/style.css   # Custom styles
│   └── js/app.js       # Frontend JavaScript (abcjs rendering, download)
├── requirements.txt    # Python dependencies
└── .env.example        # Example environment variables
```

---

## How It Works

```
User uploads image
        │
        ▼
POST /api/transpose
        │
        ├─ copilot_client.py ──► GitHub Copilot API (gpt-4o vision)
        │                             extracts ABC notation from image
        │
        ├─ transposer.py ──────► music21
        │                             calculates interval, transposes notes
        │
        └─ JSON response ──────► browser
                                      abcjs renders original + transposed score
                                      user can download PNG
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `flask` | Web framework |
| `openai` | GitHub Copilot / Models API client |
| `music21` | Music notation parsing and transposition |
| `python-dotenv` | `.env` file loading |
| `Pillow` | Image validation helpers |

---

## License

MIT — see [LICENSE](LICENSE).