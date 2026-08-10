#!/usr/bin/env python3
"""Extract text from a PDF well enough to find a figure in it.

Two of this project's citations are PDFs - the NHTSA crash summary and the NHTS
travel survey - and they carry the inputs to the car-accident derivation, which
is the arithmetic most load-bearing on the comparisons page.

This uses pypdf, and does not attempt a fallback. An earlier version shipped a
small hand-rolled reader for the case where pypdf was absent: it inflated the
document's streams and harvested anything that looked like a string. It could
not resolve font encodings, so on the NHTSA PDF - which subsets its fonts - it
returned 1.6 MB of font names and character codes, and the checker reported that
as "the figure is not in this source". Homemade parsing of a format this
gnarly does not fail by refusing to work; it fails by producing something that
looks like an answer.

So: when pypdf is installed the PDF is read properly, and when it is absent the
check says it cannot run. `extract` reports which happened via `readable`, and a
caller that cannot read a document must report "could not read this" rather than
"the source does not say that" - those are different findings, and only one of
them is evidence about a source.

Nothing in build.py or the validator imports this, so the site still builds,
validates and deploys on a bare interpreter.

    pip install -r requirements.txt
    python3 tools/pdf_text.py file.pdf
"""

import collections
import sys

Extracted = collections.namedtuple("Extracted", "text how readable")

MISSING = ("pypdf is not installed - cannot read PDFs "
           "(pip install -r requirements.txt)")

# Words common enough that English prose is dense with them. pypdf returns text
# rather than character codes, so this is a backstop rather than the main event:
# it catches a scanned document whose pages carry images and no text layer.
_COMMON = ("the", "and", "of", "to", "in", "for", "is", "were", "was")


def readable(text):
    """Did the document yield words, or just marks on a page?

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


def _reader():
    """Import pypdf, or return None. Never raises.

    Not just ImportError: an optional dependency that is installed but broken
    must degrade to "cannot check this" rather than take down the caller. The
    sandbox this was written in has exactly that - pypdf present, its crypto
    backend unloadable, and the import dying inside pypdf's Rust extension.

    Hence BaseException. A pyo3 panic surfaces as PanicException, which inherits
    from BaseException, so `except Exception` walks straight past it and the
    validator dies on an import of something it does not even need. Keyboard
    interrupts and SystemExit are re-raised; nothing else here is worth crashing
    a health-data checker over.
    """
    try:
        import pypdf  # noqa: PLC0415 - optional, probed at runtime
        return pypdf
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:  # noqa: BLE001
        return None


def available():
    """Is the reader usable at all? Callers skip rather than guess."""
    return _reader() is not None


def extract(data):
    """Return Extracted(text, how, readable). `how` names what happened."""
    import io

    pypdf = _reader()
    if pypdf is None:
        return Extracted("", MISSING, False)
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
    except Exception as ex:  # noqa: BLE001 - a broken PDF is a finding, not a crash
        # The message, not just the class. "PdfReadError" is not a diagnosis:
        # it covers a damaged xref, an encrypted document, and a missing crypto
        # backend alike, and reporting only the class sent this investigation
        # down a wrong path once already.
        detail = str(ex).strip().replace("\n", " ")[:160] or "no detail given"
        return Extracted("", f"pypdf could not parse it: "
                             f"{type(ex).__name__}: {detail}", False)
    return Extracted(text, "pypdf", readable(text))


def selftest():
    """Check the parts of this that are ours. Returns a list of failures.

    Not a test of pypdf. Whether pypdf can read a given document is pypdf's
    business and its own test suite's; the real exercise of that is CI fetching
    the two cited PDFs. What is ours, and what decides whether a verification
    log tells the truth, is the readable/unreadable judgement and the refusal to
    crash on a missing or broken dependency. That is what is tested here, and it
    needs no PDF at all.
    """
    prose = ("In 2023 there were 6.14 million police-reported crashes in the "
             "United States, and the vehicles on the road travelled a total of "
             "3,247 billion miles, which is the denominator for the crash rate "
             "per mile driven that this comparison is built on. ") * 4
    cases = [
        ("prose", prose, True),
        # What a subset-font document looked like through the hand-rolled reader
        # this file used to carry: character codes, no words.
        ("character codes", "\x01\x02\x03\x04\x05\x06\x07\x08" * 200, False),
        # Printable but wordless - the case a control-character check misses.
        ("printable but wordless", "qz xkq zvq wjx pqz " * 200, False),
        ("empty", "", False),
        ("too short to judge", "6.14 million crashes", False),
    ]
    bad = [f"pdf_text: readable({label}) = {readable(text)}, expected {want}"
           for label, text, want in cases if readable(text) != want]

    # A missing or broken dependency is a skip, never an exception and never a
    # claim about a source.
    got = extract(b"%PDF-1.4 not really a pdf")
    if got.readable or got.text:
        bad.append(f"pdf_text: unparseable input returned {got}")
    return bad


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--selftest":
        bad = selftest()
        for b in bad:
            print(b, file=sys.stderr)
        where = "with pypdf" if available() else f"no pypdf ({MISSING})"
        print(f"pdf_text self-test: {'FAILED' if bad else 'passed'} [{where}]")
        return 1 if bad else 0
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    got = extract(open(sys.argv[1], "rb").read())
    verdict = "reads as text" if got.readable else "NOT READABLE"
    print(f"[{got.how}] {len(got.text):,} characters - {verdict}")
    print(got.text[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
