#!/usr/bin/env python3
"""Extract text from a PDF well enough to find a figure in it.

Two of this project's citations are PDFs - the NHTSA crash summary and the NHTS
travel survey - and they carry the inputs to the car-accident derivation. They
were being reported as "not text-checkable", which made the least-verifiable
anchor on the site the one whose arithmetic is most load-bearing.

Uses pypdf when it is installed, and falls back to a small pure-Python reader so
the check still runs where no dependency is available. The fallback inflates
FlateDecode streams with zlib from the standard library and pulls the operands
of the text-showing operators. That is not a PDF parser: it does not handle
custom font encodings, and a PDF that subsets its fonts with a non-standard
encoding will come out as mojibake. It is enough to answer "does the string
6.14 appear in this document", which is all the claim check asks.

    python3 tools/pdf_text.py file.pdf
"""

import re
import sys
import zlib

# Text-showing operators: (string) Tj | (string) ' | (string) " | [array] TJ
_TJ = re.compile(rb"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>")
_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.S)

_ESCAPES = {
    b"\\n": b"\n", b"\\r": b"\r", b"\\t": b"\t", b"\\b": b"\b",
    b"\\f": b"\f", b"\\(": b"(", b"\\)": b")", b"\\\\": b"\\",
}


def _unescape(raw):
    for a, b in _ESCAPES.items():
        raw = raw.replace(a, b)
    # \ddd octal escapes
    return re.sub(rb"\\([0-7]{1,3})",
                  lambda m: bytes([int(m.group(1), 8) & 0xFF]), raw)


def _from_literal(tok):
    if tok.startswith(b"<"):
        hexed = re.sub(rb"[^0-9A-Fa-f]", b"", tok)
        if len(hexed) % 2:
            hexed += b"0"
        try:
            return bytes.fromhex(hexed.decode("ascii"))
        except ValueError:
            return b""
    return _unescape(tok[1:-1])


def _pure_python(data):
    """Inflate every stream we can and harvest text-operator operands."""
    out = []
    for m in _STREAM.finditer(data):
        chunk = m.group(1)
        for candidate in (chunk, chunk.strip(b"\r\n")):
            try:
                chunk = zlib.decompress(candidate)
                break
            except zlib.error:
                continue
        else:
            # Uncompressed streams are usable as-is; anything else we skip.
            if b"Tj" not in chunk and b"TJ" not in chunk:
                continue
        for tok in _TJ.findall(chunk):
            piece = _from_literal(tok)
            if piece:
                out.append(piece.decode("latin-1", "replace"))
    return " ".join(out)


def extract(data):
    """Return (text, how). `how` names the path taken, for honest reporting."""
    try:
        import io

        import pypdf  # noqa: PLC0415 - optional, probed at runtime
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        if text.strip():
            return text, "pypdf"
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - a broken PDF should fall through, not crash
        pass
    return _pure_python(data), "built-in fallback (no font decoding)"


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    text, how = extract(open(sys.argv[1], "rb").read())
    print(f"[{how}] {len(text):,} characters")
    print(text[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
