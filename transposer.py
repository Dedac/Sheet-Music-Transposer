"""
Music transposition logic using music21.

Parses ABC notation extracted from a sheet-music image, transposes every
note by the chromatic interval between the source and destination key
tonics, and writes the result back as ABC notation.
"""

import re

from music21 import chord as m21chord
from music21 import converter, interval, note as m21note
from music21 import pitch, stream


# ---------------------------------------------------------------------------
# Public keys list (used by the web UI)
# ---------------------------------------------------------------------------

MUSICAL_KEYS: list[str] = [
    # Major keys (circle of fifths order)
    "C major", "G major", "D major", "A major", "E major", "B major",
    "F# major", "C# major",
    "F major", "Bb major", "Eb major", "Ab major", "Db major", "Gb major", "Cb major",
    # Natural minor keys
    "A minor", "E minor", "B minor", "F# minor", "C# minor", "G# minor",
    "D# minor", "A# minor",
    "D minor", "G minor", "C minor", "F minor", "Bb minor", "Eb minor", "Ab minor",
]

# Map tonic names → ABC key field values  (major = bare name, minor = name + 'm')
_ABC_KEY_MAP: dict[str, str] = {
    "C major": "C",   "G major": "G",   "D major": "D",   "A major": "A",
    "E major": "E",   "B major": "B",   "F# major": "F#", "C# major": "C#",
    "F major": "F",   "Bb major": "Bb", "Eb major": "Eb", "Ab major": "Ab",
    "Db major": "Db", "Gb major": "Gb", "Cb major": "Cb",
    "A minor": "Am",  "E minor": "Em",  "B minor": "Bm",  "F# minor": "F#m",
    "C# minor": "C#m","G# minor": "G#m","D# minor": "D#m","A# minor": "A#m",
    "D minor": "Dm",  "G minor": "Gm",  "C minor": "Cm",  "F minor": "Fm",
    "Bb minor": "Bbm","Eb minor": "Ebm","Ab minor": "Abm",
}


def _parse_tonic(key_str: str) -> str:
    """Return just the tonic letter (+ accidental) from 'C major' → 'C'."""
    return key_str.split()[0]


def transpose_abc(abc_notation: str, source_key: str, dest_key: str) -> str:
    """
    Transpose *abc_notation* from *source_key* to *dest_key*.

    Strategy
    --------
    1. Parse the ABC string with music21.
    2. Transpose the resulting Stream by the chromatic interval between
       the two key tonics.
    3. Serialise the transposed Stream back to ABC notation using a
       custom generator (music21 ≥ 9 does not natively write ABC).
    4. Fall back to a header-only patch when parsing fails — at minimum
       the K: line is updated so abcjs can display the score.

    Parameters
    ----------
    abc_notation : ABC notation string (may include header fields)
    source_key   : e.g. "C major"
    dest_key     : e.g. "G major"

    Returns
    -------
    Transposed ABC notation string.
    """
    src_tonic = _parse_tonic(source_key)
    dst_tonic = _parse_tonic(dest_key)

    trans_interval = interval.Interval(
        pitch.Pitch(src_tonic),
        pitch.Pitch(dst_tonic),
    )

    try:
        score = converter.parse(abc_notation, format="abc")
        transposed = score.transpose(trans_interval)
        result = _stream_to_abc(transposed, dest_key)
        return result
    except Exception:
        pass

    # Fallback: patch only the K: header
    return _patch_key_header(abc_notation, dest_key)


# ---------------------------------------------------------------------------
# ABC serialiser
# ---------------------------------------------------------------------------

# Duration mapping: quarterLength → ABC multiplier relative to L:1/8
# L:1/8 means 1 unit = 1 eighth note = quarterLength 0.5
_DURATION_MAP: list[tuple[float, str]] = [
    (4.0,  "8"),   # whole note
    (3.0,  "6"),   # dotted half
    (2.0,  "4"),   # half note
    (1.5,  "3"),   # dotted quarter
    (1.0,  "2"),   # quarter note
    (0.75, "3/2"), # dotted eighth – rare; render as nearest
    (0.5,  ""),    # eighth note (default, no multiplier needed)
    (0.25, "/2"),  # sixteenth note
    (0.125,"/4"),  # thirty-second note
]


def _quarter_to_abc_dur(ql: float) -> str:
    """Convert a music21 quarterLength to an ABC duration token (assumes L:1/8)."""
    best = ""
    best_diff = float("inf")
    for val, token in _DURATION_MAP:
        diff = abs(ql - val)
        if diff < best_diff:
            best_diff = diff
            best = token
    return best


# ABC note name table: pitch class → base letter
_PITCH_TO_ABC_BASE = {
    "C": "C", "D": "D", "E": "E", "F": "F",
    "G": "G", "A": "A", "B": "B",
}

# ABC uses: ^ sharp, ^^ double-sharp, _ flat, __ double-flat, = natural
_ACCIDENTAL_TO_ABC = {
    "sharp": "^",
    "double-sharp": "^^",
    "flat": "_",
    "double-flat": "__",
    "natural": "=",
    "half-sharp": "^",   # approximate
    "half-flat": "_",    # approximate
}


def _pitch_to_abc(p: pitch.Pitch) -> str:
    """Convert a music21 Pitch object to an ABC note token."""
    base_name = p.step          # e.g. "C", "F"
    octave    = p.octave        # e.g. 4, 5

    acc_token = ""
    if p.accidental is not None:
        acc_token = _ACCIDENTAL_TO_ABC.get(p.accidental.name, "")

    # ABC reference: C=C4 (middle C) is uppercase C without suffix.
    # Octave 4 → uppercase, no suffix
    # Octave 5 → lowercase, no suffix
    # Octave 3 → uppercase + ","
    # Octave 6 → lowercase + "'"
    if octave == 4:
        letter = base_name.upper()
        suffix = ""
    elif octave == 5:
        letter = base_name.lower()
        suffix = ""
    elif octave >= 6:
        letter = base_name.lower()
        suffix = "'" * (octave - 5)
    elif octave == 3:
        letter = base_name.upper()
        suffix = ","
    else:
        letter = base_name.upper()
        suffix = "," * (4 - octave)

    return f"{acc_token}{letter}{suffix}"


def _stream_to_abc(score: stream.Score, dest_key: str) -> str:
    """Serialise a transposed music21 Score to an ABC notation string."""
    abc_key_val = _ABC_KEY_MAP.get(dest_key, _parse_tonic(dest_key))

    # Collect header
    lines = [
        "X:1",
        "T:Transposed Score",
    ]

    # Try to read time signature from the score
    time_sigs = score.flatten().getElementsByClass("TimeSignature")
    if time_sigs:
        ts = time_sigs[0]
        lines.append(f"M:{ts.numerator}/{ts.denominator}")
    else:
        lines.append("M:4/4")

    lines.append("L:1/8")
    lines.append(f"K:{abc_key_val}")

    # Collect notes / rests / chords from the flattened stream
    elements = list(score.flatten().notesAndRests)
    if not elements:
        lines.append("|]")
        return "\n".join(lines) + "\n"

    # Group into bars (simple approach: count quarter-lengths per bar)
    time_sigs2 = score.flatten().getElementsByClass("TimeSignature")
    bar_ql = 4.0  # default: 4/4 = 4 quarter-lengths per bar
    if time_sigs2:
        ts2 = time_sigs2[0]
        bar_ql = ts2.barDuration.quarterLength

    bar_tokens: list[str] = []
    current_bar: list[str] = []
    current_ql  = 0.0

    for el in elements:
        if isinstance(el, m21note.Note):
            token = _pitch_to_abc(el.pitch) + _quarter_to_abc_dur(el.quarterLength)
        elif isinstance(el, m21chord.Chord):
            # Render chord as the highest-pitch note
            top = max(el.pitches, key=lambda p: p.ps)
            token = _pitch_to_abc(top) + _quarter_to_abc_dur(el.quarterLength)
        elif isinstance(el, m21note.Rest):
            token = "z" + _quarter_to_abc_dur(el.quarterLength)
        else:
            continue

        current_bar.append(token)
        current_ql += el.quarterLength

        if current_ql >= bar_ql:
            bar_tokens.append(" ".join(current_bar))
            current_bar = []
            current_ql  = 0.0

    if current_bar:
        bar_tokens.append(" ".join(current_bar))

    # Join bars with | and terminate
    body = "|".join(bar_tokens)
    if not body.startswith("|"):
        body = "|" + body
    body += "|]"

    lines.append(body)
    return "\n".join(lines) + "\n"


def _patch_key_header(abc: str, dest_key: str) -> str:
    """Replace (or insert) the K: header line to match *dest_key*."""
    abc_key_val = _ABC_KEY_MAP.get(dest_key, _parse_tonic(dest_key))

    if re.search(r"^K:", abc, re.MULTILINE):
        abc = re.sub(r"^K:.*$", f"K:{abc_key_val}", abc, flags=re.MULTILINE)
    else:
        # Insert before the first non-header line (music body)
        abc = abc.rstrip() + f"\nK:{abc_key_val}\n"

    return abc
