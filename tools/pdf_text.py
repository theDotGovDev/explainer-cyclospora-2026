#!/usr/bin/env python3
"""Extract text from a PDF well enough to find a figure in it.

Two of this project's citations are PDFs - the NHTSA crash summary and the NHTS
travel survey - and they carry the inputs to the car-accident derivation. They
were being reported as "not text-checkable", which made the least-verifiable
anchor on the site the one whose arithmetic is most load-bearing.

Uses pypdf when it is installed, and falls back to a small pure-Python reader so
the check still runs where no dependency is available. The fallback inflates
FlateDecode streams with zlib from the standard library and pulls the operands
of the text-showing operators. That is not a PDF parser: it does not resolve
font encodings, so a document that subsets its fonts with a custom encoding
comes out as mojibake.

The important part is that it SAYS SO. `extract` returns a `readable` flag, and
a caller that cannot read a document must report "could not read this" rather
than "the figure is not in here" - those are different findings, and only one of
them is evidence about the source.

    python3 tools/pdf_text.py file.pdf
"""

import collections
import re
import sys
import zlib

Extracted = collections.namedtuple("Extracted", "text how readable")

# Text-showing operators: (string) Tj | (string) ' | (string) " | [array] TJ
_TJ = re.compile(rb"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>")
_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.S)

_ESCAPES = {
    b"\\n": b"\n", b"\\r": b"\r", b"\\t": b"\t", b"\\b": b"\b",
    b"\\f": b"\f", b"\\(": b"(", b"\\)": b")", b"\\\\": b"\\",
}

# Streams that are not page content but do contain parenthesised strings, so a
# naive harvest scoops them up and buries the actual text. A ToUnicode CMap is
# the worst of these: it is a table of font names and character codes, which is
# exactly what "Identity Adobe Symbol Identity Adobe Wingdings Arial" is.
_NOT_CONTENT = (b"begincmap", b"/CIDInit", b"<?xpacket", b"endcmap")
_FONT_MAGIC = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf", b"\x80\x01",
               b"%!PS")

# Words common enough that prose in English is dense with them. Their absence
# from a large body of extracted text means the bytes were never decoded into
# words, whatever they look like.
_COMMON = ("the", "and", "of", "to", "in", "for", "is", "were", "was")


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


def _is_content(chunk):
    """Is this stream page content, rather than a font, CMap or metadata blob?"""
    if chunk.startswith(_FONT_MAGIC):
        return False
    head = chunk[:4000]
    if any(marker in head for marker in _NOT_CONTENT):
        return False
    # Text can only be shown inside a BT/ET block, so a content stream that has
    # any text in it has a BT. This is a positive test, which fails safe: an
    # unrecognised stream is skipped rather than harvested as noise.
    return b"BT" in chunk


def _pure_python(data):
    """Inflate page-content streams and harvest text-operator operands."""
    out = []
    for m in _STREAM.finditer(data):
        chunk = m.group(1)
        for candidate in (chunk, chunk.strip(b"\r\n")):
            try:
                chunk = zlib.decompress(candidate)
                break
            except zlib.error:
                continue
        if not _is_content(chunk):
            continue
        for tok in _TJ.findall(chunk):
            piece = _from_literal(tok)
            if piece:
                out.append(piece.decode("latin-1", "replace"))
    return " ".join(out)


def readable(text):
    """Did the bytes come out as words, or as undecoded character codes?

    Deliberately conservative. Callers use this to downgrade a "figure not
    found" into "could not read the document", so a false negative costs a
    verification we could have had, while a false positive would let the checker
    claim a source does not say something it may well say.
    """
    text = text.strip()
    if len(text) < 200:
        return False
    noise = sum(1 for ch in text if not (ch.isprintable() or ch.isspace()))
    if noise / len(text) > 0.02:
        return False
    low = " " + text.lower() + " "
    hits = sum(low.count(f" {w} ") for w in _COMMON)
    # Ordinary English runs well over ten of these per thousand characters.
    # Half of one is a floor that only text with no words in it fails.
    return hits >= 0.5 * (len(text) / 1000)


def extract(data):
    """Return Extracted(text, how, readable). `how` names the path taken."""
    try:
        import io

        import pypdf  # noqa: PLC0415 - optional, probed at runtime
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        if text.strip():
            return Extracted(text, "pypdf", readable(text))
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - a broken PDF should fall through, not crash
        pass
    text = _pure_python(data)
    return Extracted(text, "built-in fallback (no font decoding)", readable(text))


def _pdf(streams):
    """Assemble a minimal PDF around the given raw streams, for the self-test."""
    out = [b"%PDF-1.4\n"]
    for s in streams:
        out.append(b"1 0 obj\n<< /Length %d >>\nstream\n" % len(s)
                   + s + b"\nendstream\nendobj\n")
    return b"".join(out)


def selftest():
    """Check the fallback on documents whose right answer is known.

    Returns a list of failure strings. The two cases that matter are the two
    the real citations exercise: a document whose text decodes, which must be
    searchable, and a document whose fonts do not decode, which must be
    reported as unreadable rather than as a source that omits the figure.
    """
    import zlib as _zlib

    prose = (b"BT (In 2023 there were 6.14 million police-reported crashes, and "
             b"the vehicles on the road travelled 3,247 billion miles in total, "
             b"which is the denominator for the crash rate. ) Tj ET ") * 6
    cmap = (b"/CIDInit /ProcSet findresource begin begincmap /CMapName "
            b"/Identity-H def /Registry (Adobe) /Ordering (Symbol) "
            b"(Wingdings) (Arial) (Times New Roman) endcmap ") * 40
    codes = b"BT <0102030405060708090A0B0C0D0E0F1011121314> Tj ET " * 60
    font = b"\x00\x01\x00\x00 BT (glyf loca cmap head) Tj ET"

    bad = []
    for label, doc, want_readable, want_in, want_out in (
        ("uncompressed text", _pdf([prose]), True, ["6.14", "3,247"], []),
        ("deflated text", _pdf([_zlib.compress(prose)]), True, ["6.14"], []),
        ("undecodable fonts", _pdf([cmap, codes]), False, [], ["Adobe", "Arial"]),
        ("font programme beside text", _pdf([font, prose]), True, ["6.14"], ["glyf"]),
    ):
        got = extract(doc)
        if got.readable != want_readable:
            bad.append(f"pdf_text: {label}: readable={got.readable}, "
                       f"expected {want_readable}")
        for s in want_in:
            if s not in got.text:
                bad.append(f"pdf_text: {label}: {s!r} missing from extracted text")
        for s in want_out:
            # A font table or CMap harvested as if it were page text is how the
            # NHTSA citation came back as 1.6 MB of font names.
            if s in got.text:
                bad.append(f"pdf_text: {label}: {s!r} leaked out of a non-content "
                           f"stream into the extracted text")
    return bad


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        bad = selftest()
        for b in bad:
            print(b, file=sys.stderr)
        print("pdf_text self-test: " + ("FAILED" if bad else "passed"))
        return 1 if bad else 0
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    got = extract(open(sys.argv[1], "rb").read())
    verdict = "reads as text" if got.readable else "NOT DECODABLE - install pypdf"
    print(f"[{got.how}] {len(got.text):,} characters - {verdict}")
    print(got.text[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
