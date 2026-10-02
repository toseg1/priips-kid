"""Regex field extractors for PRIIPs KID documents.

Regexes are anchored on PRIIPs-mandated section headings (Type:, Term:,
Recommended holding period, Composition of Costs, ...), which are consistent
across issuers. Verified against 4 templates (iShares/BlackRock x2, Amundi,
L&G/LGIM) -- a new issuer template may need additional fallback patterns.
French-language KIDs have their own extractors in kid_parser.fields_fr.

Every function here takes the already-normalized ("flat") document text (see
kid_parser.text.normalize_flat) and returns a plain value / tuple / dict --
no dataclasses at this layer. kid_parser.parser assembles these into the
KidDocument model.
"""

import re

from .text import CURRENCY_NAME_TO_CODE, MONEY, clean, find, find_rate_pct, parse_money, share_class_from_name

FILENAME_RE = re.compile(
    r"PRP_(?P<country>[A-Z]{2})_(?P<lang>[a-z]{2})_(?P<isin>[A-Z0-9]{12})_"
    r"(?P<flag>[A-Z]+)_(?P<date>\d{4}-\d{2}-\d{2})"
)

SCENARIO_NAMES = ["Stress", "Unfavourable", "Moderate", "Favourable"]

BOILERPLATE = [
    r"Ongoing costs taken each year\s*",
    r"One-off costs upon entry or exit\s*",
    r"Incidental costs taken under specific conditions\s*",
]

# Case-sensitive (real table headers are capitalized) with a negative
# lookbehind for a preceding quote, since the surrounding prose sometimes
# quotes a header name inline (e.g. "...under 'Transaction costs'.").
COST_CATEGORIES = [
    ("entry_costs", r"(?<!['\"])Entry costs\*?"),
    ("exit_costs", r"(?<!['\"])Exit costs\*?"),
    ("management_fees", r"(?<!['\"])Management fees and other\s*administrative or\s*operating costs"),
    ("transaction_costs", r"(?<!['\"])Transaction costs"),
    ("performance_fees", r"(?<!['\"])Performance fees(?:\s+and\s+carried\s+interest)?"),
]


def parse_filename(stem):
    m = FILENAME_RE.search(stem)
    return m.groupdict() if m else {}


MONTHS = {
    m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"], start=1)
}


def extract_production_date(flat, filename_date=None):
    m = re.search(r"\bdated (\d{1,2}) ([A-Za-z]+) (\d{4})", flat)
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return filename_date


def extract_is_ucits(flat):
    head = flat[:4000]
    if re.search(r"\bUCITS\b|Undertaking for Collective Investment in Transferable Securities", head):
        return True
    if re.search(r"\bAIF\b|Alternative Investment Fund", head):
        return False
    return None


def extract_isin(flat, filename_isin):
    if filename_isin:
        return filename_isin
    m = re.search(r"ISIN:?\s*([A-Z]{2}[A-Z0-9]{9}\d)", flat)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b", flat)
    return m.group(1) if m else None


def extract_product_and_class(product_section):
    if not product_section:
        return None, None
    m = re.search(
        r'([^.]+?)\s*\(the\s*"Fund"\),\s*([^,(]+?)\s*\(the\s*"Share Class"\)',
        product_section,
    )
    if m:
        return clean(m.group(1)), clean(m.group(2))
    # L&G-style: labeled fields ("Name of Fund: ... Share class name: ...")
    # rather than prose - must be checked before the generic UCITS fallback
    # below, since that one greedily matches into these labels too.
    m = re.search(
        r"Name of Fund:\s*(.+?)\s*(?:This PRIIP|Share class name:|Manufacturer name:)",
        product_section,
        re.I,
    )
    if m:
        name = clean(m.group(1))
        cm = re.search(
            r"Share class name:\s*(.+?)\s*(?:Website:|Manufacturer name:|Telephone:|Regulator:|$)",
            product_section,
            re.I,
        )
        return name, clean(cm.group(1)) if cm else None
    # Amundi-style: no quoted Share Class - product name is the first
    # sentence-like chunk; the class is its suffix ("... UCITS ETF Acc")
    m = re.match(r"\s*([A-Z][^.]*?UCITS[^.]*?)(?:\s+A Sub-Fund of|\s+ISIN|\.)", product_section)
    if m:
        name = clean(m.group(1))
        return name, share_class_from_name(name)
    return None, None


def extract_issuer(flat):
    m = re.search(r"manufactured by ([^(]+)\(", flat)
    if m:
        return clean(m.group(1))
    m = re.search(r"Management Company:\s*([^(]+?)\s*\(", flat)
    if m:
        return clean(m.group(1))
    m = re.search(r"Manufacturer name:\s*(.+?)(?:,\s*part of|\s*Telephone:|\s*Regulator:)", flat, re.I)
    if m:
        return clean(m.group(1))
    return None


def extract_website(flat):
    m = re.search(r"\bwww\.[^\s,;)]+", flat)
    return clean(m.group(0).rstrip(".")) if m else None


def extract_phone(flat):
    m = re.search(r"(?:calling|call|hotline on)\s+([+0-9][0-9 ]{6,}\d)", flat, re.I)
    if m:
        return clean(m.group(1))
    m = re.search(r"Telephone:\s*([+0-9][0-9 ()]*\d)", flat, re.I)
    return clean(m.group(1)) if m else None


def extract_email(flat):
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", flat)
    return clean(m.group(0).rstrip(".")) if m else None


def extract_product_section(flat):
    # "Product" (capitalized, exact word) is the heading; matched
    # case-sensitively so it isn't confused with the common noun "product"/
    # "products" used throughout the surrounding prose.
    return find(r"\bProduct\s+(.*?)\s*What is this product\?", flat, flags=0)


def extract_type(flat):
    return find(r"Type:\s*(.*?)\s*Term:", flat)


def extract_term(flat):
    return find(r"Term:\s*(.*?)(?=Objectives)", flat)


def extract_objective(flat):
    return find(
        r"Objectives:?\s*(.*?)(?=Intended [Rr]etail [Ii]nvestor|Redemption and Dealing)",
        flat,
    )


def extract_custodian(flat):
    m = re.search(r"[Dd]epositary(?: of the (?:Fund|Sub-Fund))? is ([^.]+?)(?:\s*\(the|\.)", flat)
    if m:
        return clean(m.group(1))
    m = re.search(r"Depositary:\s*([^.\n]+)", flat)
    return clean(m.group(1)) if m else None


def extract_index(flat):
    m = re.search(r"reflects? the return of ([^,(]+)", flat, re.I)
    if m:
        return clean(m.group(1))
    m = re.search(r"track(?:s|ing)? the performance of ([^(]+?)\s*\(", flat, re.I)
    return clean(m.group(1)) if m else None


def extract_currency(flat):
    # no trailing \b: pypdf sometimes glues the next word directly onto the
    # code (e.g. "Currency: USDThis Sub-Fund..."), but the {3} count already
    # bounds the capture to exactly the code.
    m = re.search(r"\bCurrency:\s*([A-Z]{3})", flat)
    if m:
        return m.group(1)
    m = re.search(r"denominated in ([A-Za-z ]+?),\s*the Fund", flat)
    if m:
        return CURRENCY_NAME_TO_CODE.get(m.group(1).strip().lower())
    # L&G-style: "...are denominated in USD and can be..." - code directly,
    # no ", the Fund's base currency" continuation.
    m = re.search(r"denominated in ([A-Z]{3})\b", flat)
    if m:
        return m.group(1)
    return None


def extract_sfdr_article(flat):
    m = re.search(r"Article\s*(6|8|9)\s*of the (?:SFDR|Disclosure Regulation)", flat, re.I)
    return f"Article {m.group(1)}" if m else None


def extract_distribution_policy(flat):
    # "non-distributing"/"accumulation" wins even when the surrounding prose
    # also contains the word "distributing" (e.g. Amundi describes an
    # accumulating share class as "a non-distributing share class").
    if re.search(r"accumulat|non-distributing", flat, re.I):
        return "Accumulating"
    if re.search(r"\bdistributing\b", flat, re.I):
        return "Distributing"
    return None


def extract_intended_for(flat):
    # "Intended retail investor" is a mandatory PRIIPs heading present on
    # essentially every one of these documents regardless of this fund's
    # actual audience (PRIIPs KIDs are, by definition, for retail products),
    # so it carries no information and must not be used as the signal.
    # Only the descriptive sentence that follows the heading is classified.
    body = find(
        r"Intended\s+[A-Za-z/ ]*Investor:?\s*(.*?)"
        r"(?=Insurance benefits|Redemption and Dealing|What are the risks)",
        flat,
    ) or ""
    is_retail = bool(re.search(r"\bretail\b", body, re.I))
    is_professional = bool(
        re.search(r"professional|institutional|eligible counterpart|qualified investor", body, re.I)
    )
    if is_retail and is_professional:
        return "Retail/Professional"
    if is_retail:
        return "Retail"
    if is_professional:
        return "Professional"
    return None


def extract_sri(flat):
    m = re.search(r"classified this product as\s*(\d)\s*out of\s*7", flat, re.I)
    return int(m.group(1)) if m else None


def extract_rhp_years(flat):
    patterns = [
        r"Recommended [Hh]olding [Pp]eriod\s*:?\s*(\d+)\s*years?",
        r"recommended holding period of\s*(\d+)\s*years?",
        r"(\d+)\s*years?\s*\(Recommended holding\s*period\)",
    ]
    for pattern in patterns:
        m = re.search(pattern, flat, re.I)
        if m:
            return int(m.group(1))
    return None


def extract_example_investment(flat):
    m = re.search(r"(?:Example )?Investment\s*:?\s*(EUR|USD|GBP|CHF)\s*([\d,]+(?:\.\d+)?)", flat)
    if not m:
        return None
    return {"currency": m.group(1), "value": float(m.group(2).replace(",", ""))}


def extract_scenario_time_frame(rhp_years):
    # PRIIPs KIDs always show 1 year as the short exit period; the
    # recommended period is the RHP, already extracted reliably from its own
    # "Recommended holding period : N years" sentence (more robust than
    # re-parsing "exit after" table headers, whose layout varies by template).
    return {
        "short": "1 year",
        "recommended": f"{rhp_years} years" if rhp_years else None,
    }


def extract_scenarios(flat):
    scenarios = {}
    for name in SCENARIO_NAMES:
        # \b before the name keeps "Favourable" from matching inside "Unfavourable"
        # (there's no word-boundary between "Un" and "favourable", so \b alone
        # rejects that position; case-sensitivity below is the actual guard).
        # The optional "scenario" word and asterisks can appear in either
        # order depending on the issuer (e.g. "Stress* ..." vs "Stress
        # Scenario ..." vs "Stress scenario* ...").
        pattern = (
            rf"\b{name}\b\s*(?:[Ss]cenario)?\s*\**\s*What you might get back after costs\s+"
            rf"{MONEY}\s+{MONEY}\s+Average return each year\s+(-?[\d.]+)%\s+(-?[\d.]+)%"
        )
        m = re.search(pattern, flat)
        if not m:
            scenarios[name.lower()] = None
            continue
        sym1, amt1, code1, sym2, amt2, code2, pct1, pct2 = m.groups()
        money_1y = parse_money(sym1, amt1, code1)
        money_rhp = parse_money(sym2, amt2, code2)
        scenarios[name.lower()] = {
            "1y": {**money_1y, "return_pct": float(pct1)} if money_1y else None,
            "rhp": {**money_rhp, "return_pct": float(pct2)} if money_rhp else None,
        }
    return scenarios


def extract_cost_example_investment(flat):
    # The costs table restates its own example investment amount ("EUR
    # 10,000 is invested." / "USD 10,000 invested.") separately from the
    # Performance Scenarios section's amount - kept distinct in case an
    # issuer ever uses a different amount for the two illustrations.
    m = re.search(r"What are the costs\?(.*)", flat, re.I)
    section = m.group(1) if m else flat
    m2 = re.search(r"(EUR|USD|GBP|CHF)\s*([\d,]+(?:\.\d+)?)\s*(?:is\s+)?invested", section, re.I)
    if not m2:
        return None
    return {"currency": m2.group(1).upper(), "value": float(m2.group(2).replace(",", ""))}


def extract_total_costs(flat):
    pattern = (
        rf"Total [Cc]osts\s+{MONEY}\s+{MONEY}\s+"
        rf"(?:Annual [Cc]ost [Ii]mpact|Impact on return \(RIY\) per year).*?(-?[\d.]+)%\s+(-?[\d.]+)%"
    )
    m = re.search(pattern, flat, re.I)
    if not m:
        return None, None, None, None
    sym1, amt1, code1, sym2, amt2, code2, pct1, pct2 = m.groups()
    return (
        parse_money(sym1, amt1, code1),
        parse_money(sym2, amt2, code2),
        float(pct1),
        float(pct2),
    )


def extract_cost_breakdown(flat):
    m = re.search(
        r"Composition of Costs(.*?)(?=How long should I hold|$)",
        flat,
        re.I,
    )
    section = m.group(1) if m else flat

    boundaries = []
    for key, label_pattern in COST_CATEGORIES:
        bm = re.search(label_pattern, section)
        if bm:
            boundaries.append((bm.start(), bm.end(), key))
    boundaries.sort()

    breakdown = {key: {"description": None, "pct": None, "amount": None} for key, _ in COST_CATEGORIES}
    for i, (_, end, key) in enumerate(boundaries):
        chunk_end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(section)
        chunk = section[end:chunk_end]
        for boilerplate in BOILERPLATE:
            chunk = re.sub(boilerplate, "", chunk)
        flat_chunk = re.sub(r"\s+", " ", chunk).strip()
        # drop a footnote reference glued directly onto a sentence (e.g.
        # "entry fee.1" -> "entry fee.")
        flat_chunk = re.sub(r"\.(\d)(?=\s|$)", ".", flat_chunk)

        pct_m = re.search(r"([\d.]+)%", flat_chunk)
        pct = float(pct_m.group(1)) if pct_m else None

        amount = None
        amount_start = None
        for mm in reversed(list(re.finditer(MONEY, flat_chunk))):
            sym, amt, code = mm.groups()
            parsed = parse_money(sym, amt, code)
            if parsed and parsed["currency"]:
                amount = parsed
                amount_start = mm.start()
                break

        if amount_start is not None:
            # the amount is already captured separately - don't repeat it
            # (or the footnote text that trails it) in the description
            description_text = flat_chunk[:amount_start]
        else:
            # no real amount (a "-" placeholder): still cut off a trailing
            # footnote paragraph glued on without a space, e.g. "...for this
            # product. -1Not applicable to secondary market investors..."
            footnote_m = re.search(r"\d(?=[A-Z][a-z])|\*\s+[A-Z][a-z]+(?:\s[A-Z][a-z]+)*:", flat_chunk)
            description_text = flat_chunk[:footnote_m.start()] if footnote_m else flat_chunk

        # "Up to 0 USD" - drop the lead-in phrase left dangling once the
        # amount itself is cut off.
        description_text = re.sub(r"\bUp to\s*$", "", description_text, flags=re.I)
        description_text = re.sub(r"[\s\-]+$", "", description_text)

        breakdown[key] = {
            "description": clean(description_text) or None,
            "pct": pct,
            "amount": amount,
        }
        if key == "performance_fees":
            performance_chunk = flat_chunk

    performance_desc = (breakdown["performance_fees"]["description"] or "")
    performance_fees_yn = not bool(
        re.search(r"no performance fee", performance_desc, re.I)
    ) if performance_desc else None
    if performance_fees_yn:
        # pct is the fee rate (% of outperformance), not its cost impact
        rate_m = find_rate_pct(performance_chunk, r"([\d.]+)%", r"performance")
        breakdown["performance_fees"]["pct"] = float(rate_m.group(1)) if rate_m else None

    return breakdown, performance_fees_yn
