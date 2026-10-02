# kid-parser

Regex-only parser for PRIIPs Key Information Documents (KIDs) — no LLM, no API
keys. Reads a KID PDF straight from `pypdf` text extraction and returns a
typed `KidDocument` (product info, costs, risk, performance scenarios, ...).

## Install

```bash
pip install "kid-parser @ git+https://github.com/toseg1/kid-parser.git@v0.2.0"
```

## Usage

```python
from kid_parser import parse_kid, parse_kids, KidDocument

kid = parse_kid("IE00BL6K8D99.pdf")   # -> KidDocument, no disk writes
kid.isin                              # "IE00BL6K8D99"
kid.share_class                       # "EUR Accu"
kid.cost_section.total_cost_1y.value  # 18.0
kid.language, kid.production_date     # ("en", "2026-04-09")
kid.is_ucits                          # True

kids = parse_kids("path/to/kids_dir") # -> list[KidDocument]

# JSON is opt-in (de)serialization, not a side effect of parsing:
json_str = kid.to_json()
kid2 = KidDocument.from_json(json_str)      # round-trip from a string
kid3 = KidDocument.from_json("saved.json")  # or from a file, no PDF needed
```

CLI mirrors this — JSON is only written if you ask for it:

```bash
kid-parser some/*.pdf                  # one-line summaries, nothing written
kid-parser some_dir/ --json-dir out/   # + <isin>.kid.json and kids_parsed.json
kid-parser some_dir/ --json            # combined JSON array to stdout
```

## Coverage

Regexes are anchored on PRIIPs-mandated section headings, so they should
generalize, but each issuer phrases things slightly differently. Tested so
far against real KIDs from:

- **BlackRock / iShares**
- **Amundi**
- **L&G / LGIM**

French-language KIDs ("Document d'informations clés") are detected
automatically and parsed with their own pattern set
(`src/kid_parser/fields_fr.py`), tested against:

- **Crédit Mutuel Asset Management** (OPCVM and FIA)
- **Robeco**
- **FFG / Waystone**
- **La Française**
- **Eiffel Investment Group** (ELTIF)
- **BlackRock / iShares** and **Amundi** (French versions of their KIDs)
- **CPR Asset Management**
- **ODDO BHF Asset Management**
- **Natixis Investment Managers** (Mirova)
- **Indépendance AM**
- **Société Générale Investment Solutions** (Bourso Invest FIVG)

French issuers mix three number formats ("10 000 €", "10.000 EUR",
"10,000 EUR"); amounts with exactly three digits after a separator are read
as thousands, everything else as decimals. The currency may also come first
("€4 380", "EUR 10 000").

In the cost breakdown, `pct` is the impact on your investment for every row
except performance fees, where it is the fee rate (e.g. 20 % of the
outperformance) and `amount` is the real EUR amount from the cost table. Scenario keys stay in English
(`stress`, `unfavourable`, `moderate`, `favourable`) whatever the language.

## Contributing

New issuer templates almost always need a small regex fallback somewhere in
`src/kid_parser/fields.py` (see the existing per-issuer comments for
examples). Contributions welcome for:

- KIDs from other providers (Vanguard, DWS, SPDR, Invesco, Fidelity, ...) —
  ideally as a new fixture in `tests/fixtures/` plus a golden-value test in
  `tests/test_kid_parser.py`.
- Additional fields not yet extracted, or better handling of fields that
  currently fall back to `None`.
- Non-UCITS-ETF PRIIPs (structured products, insurance-based investment
  products) — these likely use a different template family entirely.

If a field comes back wrong or `None` for a new provider, please include the
PDF (or the relevant excerpt) in the issue/PR so the pattern can be fixed
against real text.
