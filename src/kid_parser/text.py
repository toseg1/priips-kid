"""Text extraction and normalization helpers shared by kid_parser.fields."""

import re

from pypdf import PdfReader

NORMALIZE_MAP = {
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff",
    "–": "-", "—": "-",
    # French KIDs (Crédit Mutuel AM) render every hyphen and minus sign as
    # a soft hyphen, usually padded with spaces ("CM ­AM", "­79,7 %").
    "\u00ad": "-",
    "\u00a0": " ", "\u202f": " ",
}

CURRENCY_NAME_TO_CODE = {
    "us dollar": "USD", "euro": "EUR", "pound sterling": "GBP",
    "british pound": "GBP", "swiss franc": "CHF", "japanese yen": "JPY",
}

SYMBOL_TO_CODE = {"$": "USD", "€": "EUR", "£": "GBP"}

MONEY = r"(?:([$€£])\s?)?(\d[\d,]*(?:\.\d+)?)\s?(EUR|USD|GBP|CHF)?"


def ligature_fix(text):
    for old, new in NORMALIZE_MAP.items():
        text = text.replace(old, new)
    return text


def extract_pdf_text(pdf_path):
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() for page in reader.pages)


def normalize_flat(text):
    text = ligature_fix(text)
    # pypdf sometimes drops the space between sentences across text runs
    # (e.g. "products.The information"); only fix punctuation-glued joins,
    # not general lower-upper transitions, since those also occur inside
    # legitimate camel-cased words/codes (iShares, BlackRock, IE00B4L5Y983).
    # The 2-letter lookbehind also keeps single-letter abbreviations like
    # "S.A." from being split into "S. A.".
    text = re.sub(r"(?<=[a-zA-Z]{2})([.,;:])(?=[A-Z])", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # "CM -AM" (a soft hyphen padded on one side) -> "CM-AM"; only between
    # letters, so a spaced minus sign before a number is left alone.
    text = re.sub(r"(?<=[A-Za-z]) -(?=[A-Za-z])", "-", text)
    return text


def detect_language(flat):
    if re.search(r"document d.informations cl[ée]s", flat, re.I):
        return "fr"
    return "en"


def clean(text):
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip(" .,\"'")
    return text or None


def parse_money(symbol, amount, code):
    if amount is None:
        return None
    value = float(amount.replace(",", ""))
    currency = code or SYMBOL_TO_CODE.get(symbol)
    return {"value": value, "currency": currency}


def find(pattern, text, flags=re.I, group=1):
    m = re.search(pattern, text, flags)
    return clean(m.group(group)) if m else None


# Amundi-style class suffix on the product name: up to two short code
# tokens ("S", "A EUR", "I2") then "Acc"/"Dist"/"C"/"D", with or without a
# " - " ("... UCITS ETF S - Acc" in French, "... UCITS ETF Acc" in English).
# UCITS/ETF belong to the fund name.
SHARE_CLASS_SUFFIX = re.compile(
    r"\s((?:(?!ETF\b|UCITS\b)[A-Z][A-Z0-9]{0,3}\s){0,2}(?:-\s)?(?:Acc|Dist|Inc|C|D))$"
)


def share_class_from_name(name):
    m = SHARE_CLASS_SUFFIX.search(name or "")
    return clean(m.group(1).lstrip("- ")) if m else None


def find_rate_pct(text, pct_pattern, words):
    """The performance-fee rate: the first percentage directly followed by
    performance wording ("20% maximum de la surperformance"), skipping a
    cost-impact figure printed before it ("1,52% Description : 10% lorsque
    la performance ...")."""
    matches = list(re.finditer(pct_pattern, text))
    for i, m in enumerate(matches):
        stop = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        if re.search(words, text[m.end():min(stop, m.end() + 80)], re.I):
            return m
    return None
