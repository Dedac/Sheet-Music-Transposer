"""
GitHub Copilot / GitHub Models API client for sheet music analysis.

Uses the OpenAI-compatible API exposed by GitHub Models
(https://models.inference.ai.azure.com) with a GITHUB_TOKEN for auth.
The same token works with the GitHub Copilot API endpoint when the
account has Copilot access.
"""

import os
import base64
import re
from openai import OpenAI

# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def _make_client() -> OpenAI:
    token = os.environ.get("GITHUB_TOKEN", "")
    return OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=token,
    )


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

MODEL = "gpt-4o"

EXTRACT_PROMPT = """\
You are a music transcription assistant.
Analyse the attached sheet music image and transcribe it into ABC notation.

Rules:
1. The header MUST include:
   X:1
   T:Transposed Score
   M:<time signature, e.g. 4/4>
   L:1/8
   K:<key, e.g. C for C major, Am for A minor>
2. Use standard ABC notation for every note, rest, and bar line (|).
3. Carry over any repeat signs, slurs, or ties using ABC syntax.
4. Output ONLY the raw ABC notation — no explanation, no markdown fences.

The sheet music is written in the key of {source_key}.
"""


def extract_abc_from_image(image_bytes: bytes, mime_type: str, source_key: str) -> str:
    """
    Send a sheet-music image to the Copilot/GitHub-Models API and return
    the extracted ABC notation string.

    Parameters
    ----------
    image_bytes : raw bytes of the uploaded image
    mime_type   : MIME type reported by the upload (e.g. "image/png")
    source_key  : human-readable key, e.g. "C major"

    Returns
    -------
    ABC notation string as returned by the model.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    prompt = EXTRACT_PROMPT.format(source_key=source_key)

    response = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        max_tokens=2048,
        temperature=0.2,
    )

    raw = response.choices[0].message.content or ""
    return _clean_abc(raw)


def _clean_abc(text: str) -> str:
    """Strip markdown fences and leading/trailing whitespace."""
    text = text.strip()
    # Remove ```abc ... ``` or ``` ... ``` fences if present
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()
