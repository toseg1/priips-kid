"""Regex field extractors for French-language PRIIPs KIDs ("Document
d'informations clés").

Same contract as kid_parser.fields: every function takes the normalized
("flat") text and returns plain values. Anchored on the headings the French
translation of the PRIIPs RTS mandates ("Nous avons classé ce produit dans
la classe de risque N sur 7", "Coûts totaux", "Incidence des coûts", ...).
Verified against 13 templates: Crédit Mutuel AM (OPCVM and FIA), Robeco,
FFG/Waystone, La Française, Eiffel IG, Amundi, CPR AM, BlackRock/iShares,
ODDO BHF AM, Natixis IM, Indépendance AM, Société Générale IS.

French KIDs mix three number formats depending on the issuer -- "10 000 €",
"10.000 EUR" (dot thousands, comma decimals) and "10,000 EUR" / "6.9%"
(English-style, Robeco) -- and some put the currency first ("€4 380",
"EUR 10 000"), so amounts and percentages have their own parsers below
rather than the English MONEY pattern.
"""

import re
from datetime import date

from .text import clean, find

CURRENCY = r"(€|EUR|USD|GBP|CHF)"
# A thousands group is exactly 3 digits after a space/dot/comma separator;
# anything else after a separator is a decimal part.
AMOUNT = r"(-?\d{1,3}(?:[ .,]\d{3})*(?:[.,]\d{1,2})?|-?\d+(?:[.,]\d+)?)"
MONEY_FR = AMOUNT + r"\s?" + CURRENCY
# Amundi / CPR ("€4 380"), Indépendance ("EUR 4 340"), iShares ("EUR 10.000")
MONEY_FR_PREFIX = CURRENCY + r"\s?" + AMOUNT
# One alternation so a left-to-right scan pairs each amount with its own
# currency: "€4 380 €3 350" must not read as "4 380 €" + a bare "3 350".
MONEY_FR_ANY = re.compile(r"(?:" + MONEY_FR_PREFIX + r")|(?:" + MONEY_FR + r")")
PCT_FR = r"(-?\s?\d+(?:[.,]\d+)?)\s?%"

# Scenario rows are labelled "Tensions" / "Scénario de tension(s)" etc. and
# are always followed by the table's own "Si vous sortez"/"Ce que vous
# pourriez obtenir" text -- that lookahead keeps prose mentions ("Le
# scénario de tensions montre ...") from matching. \b keeps "favorable"
# from matching inside "défavorable" ("é" is a word character).
SCENARIO_LABELS = [
    ("stress", r"(?:Sc[ée]nario de )?\b[Tt]ensions?"),
    ("unfavourable", r"(?:Sc[ée]nario )?\b[Dd]éfavorable"),
    ("moderate", r"(?:Sc[ée]nario )?\b[Ii]ntermédiaire"),
    ("favourable", r"(?:Sc[ée]nario )?\b[Ff]avorable"),
]
# Footnote markers may sit between label and row: "Défavorable**"
# (iShares), "Défavorable (*)" (Natixis).
SCENARIO_ROW_START = r"\s*(?:\(\*+\)|\*+)?\s*:?\s*(?=Si vous sortez|Ce que vous pourriez)"
SCENARIO_END = r"Ce type de sc[ée]nario|Sc[ée]nario défavorable :|Que se passe|QUE SE PASSE|Ce tableau|Les chiffres indiqués|\(?\*+\)? (?:Le|Ce) "

BOILERPLATE = [
    r"Co[ûu]ts (?:ponctuels|uniques) à l'entrée ou à la sortie\s*",
    r"Co[ûu]ts d'entrée ou de sortie ponctuels\s*",
    r"Co[ûu]ts ponctuels d'entrée ou de sortie\s*",
    r"Co[ûu]ts récurrents\s*[\[(]?(?:prélevés|encourus) chaque année[\])]?\s*",
    r"Co[ûu]ts (?:accessoires|récurrents) (?:prélevés|encourus) (?:sous certaines|dans des) conditions(?: spécifiques)?\s*",
    r"Si vous sortez après:? 1 [Aa]n\s*",
]

# Case-sensitive: the table labels are capitalized, the surrounding prose
# ("Aucun coût d'entrée n'est appliqué") is not.
COST_CATEGORIES = [
    # not iShares' "Coûts d'entrée ou de sortie ponctuels" section heading
    ("entry_costs", r"Co[ûu]ts? d'entrée(?! ou de sortie)\*?"),
    ("exit_costs", r"(?:Co[ûu]ts?|Frais) de sortie\*?"),
    # "... autres frais administratifs et d'exploitation" (most issuers),
    # "... autres coûts administratifs ou (frais) d'exploitation" (Amundi, iShares)
    ("management_fees", r"Frais de gestion et autres (?:frais|co[ûu]ts) administratifs?\s*(?:et|ou) (?:frais )?d'exploitation\.?"),
    # not the quoted cross-reference inside iShares' management-fee row
    ("transaction_costs", r"(?<!« )(?:Co[ûu]ts|Frais) de transaction"),
    ("performance_fees", r"Commissions liées aux (?:résultats|performances)(?:\s*\(?et commission d'intéressement\)?)?"),
]
CURRENCY_NAME_FR = {
    "euro": "EUR", "dollar américain": "USD", "dollar US": "USD",
    "livre sterling": "GBP", "franc suisse": "CHF",
}

INTENDED_HEADING = (
    r"INVESTISSEURS DE DETAIL VISES|Investisseurs? de détail visés?|Type d'investisseurs visés"
)

# Footnotes that follow the cost table and would otherwise leak amounts
# into the last row ("10 000 EUR sont investis", "prélèvement ... 2 %").
COST_SECTION_END = r"COMBIEN DE TEMPS|Combien de temps|Les tableaux (?:ci-dessus|présentent)|Un investisseur qui s'engage"


def parse_amount(token):
    """French/English-agnostic amount: "2 030", "10.000", "3,100" are
    thousands-grouped integers; "1,90" / "6.9" are decimals."""
    s = token.replace(" ", "")
    negative = s.startswith("-")
    s = s.lstrip("-")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        s = s.replace(".", "").replace(",", "")
    else:
        s = s.replace(",", ".")
    value = float(s)
    return -value if negative else value


def parse_pct(token):
    return float(token.replace(" ", "").replace(",", "."))


def _currency(symbol):
    return "EUR" if symbol == "€" else symbol


def _money(amount, symbol):
    return {"value": parse_amount(amount), "currency": _currency(symbol)}


def _find_money(text):
    """Every amount in `text` as (match, amount, symbol), whichever side
    the currency is written on."""
    found = []
    for m in MONEY_FR_ANY.finditer(text):
        prefix_symbol, prefix_amount, suffix_amount, suffix_symbol = m.groups()
        if prefix_amount is not None:
            found.append((m, prefix_amount, prefix_symbol))
        else:
            found.append((m, suffix_amount, suffix_symbol))
    return found


def extract_isin(flat, filename_isin):
    if filename_isin:
        return filename_isin
    m = re.search(r"ISIN[^:A-Z]{0,20}:?\s*([A-Z]{2}[A-Z0-9]{9}\d)", flat)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b", flat)
    return m.group(1) if m else None


MOIS = {
    m: i for i, m in enumerate(
        ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
         "août", "septembre", "octobre", "novembre", "décembre"], start=1)
}
MOIS.update({"fevrier": 2, "aout": 8, "decembre": 12})


def extract_production_date(flat):
    # "Date de production ... : 13/07/2026" (Indépendance: "22.07.2026"),
    # "Ce document a été publié le 01/09/2026" (CPR)
    m = re.search(
        r"(?:Date de (?:production|publication)|publié le)[^\d]{0,60}?(\d{1,2})[/.](\d{1,2})[/.](\d{4})", flat
    )
    if m:
        day, month, year = (int(g) for g in m.groups())
        return date(year, month, day).isoformat()
    # "Le présent document est daté du 09 avril 2026" (iShares),
    # "... exact et à jour au 13 avril 2026" (Natixis)
    m = re.search(r"(?:daté du|à jour au) (\d{1,2}) ([a-zéû]+) (\d{4})", flat)
    if m and m.group(2) in MOIS:
        return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1))).isoformat()
    return None


def extract_product_and_class(flat):
    # Eiffel-style labelled field
    m = re.search(r"Nom du [Pp]roduit\s*:\s*(.+?)\s*(?:Initiateur|Code ISIN)", flat)
    if m:
        name = clean(m.group(1))
        pm = re.match(r"(.+?)\s*-\s*(Part\s+\S+)$", name)
        return (clean(pm.group(1)), clean(pm.group(2))) if pm else (name, None)
    # iShares: "Produit <name> (le « Fonds ») <class> (la « Catégorie d'actions »)"
    m = re.search(r"Produit (.{3,150}?) \(le « Fonds »\) (.{2,60}?) \(la « Catégorie d'actions »\)", flat)
    if m:
        return clean(m.group(1)), clean(m.group(2))
    # Natixis: "Produit <name> un Compartiment de <umbrella> <class> (code ISIN : ...)"
    m = re.search(r"Produit (.{3,150}?) un Compartiment de .{3,100}?\s(\S+(?: \([A-Z]{3}\))?)\s*\(code ISIN", flat)
    if m:
        return clean(m.group(1)), clean(m.group(2))
    # Indépendance AM: "<umbrella> 1/3 <name> un compartiment d'<umbrella> ... Classe <class> ISIN"
    m = re.search(r"\d/\d\s+(.{3,100}?) un compartiment d'.{3,400}?Classe (.{1,20}?)\s+ISIN", flat)
    if m:
        return clean(m.group(1)), clean(m.group(2))
    # ODDO BHF: "PRODUIT <name>, Organisme ... Part <name> <class> : <ISIN>"
    m = re.search(r"PRODUIT (.{3,150}?), Organisme", flat)
    if m:
        name = clean(m.group(1))
        cm = re.search(r"Part " + re.escape(name) + r" (\S+)\s*:\s*[A-Z]{2}[A-Z0-9]{9}\d", flat)
        return name, clean(cm.group(1)) if cm else None
    # Société Générale IS (Bourso): "... ce produit ? Objectif <name> Compartiment de la SICAV"
    m = re.search(r"En quoi consiste ce produit \? Objectif (.{3,100}?) Compartiment de la SICAV", flat)
    if m:
        return clean(m.group(1)), None
    # Amundi / CPR: "Produit <name> Un Compartiment de ..." / "Produit <name>
    # Société de gestion : ...". The name keeps its class suffix; the class
    # is also reported on its own ("... UCITS ETF S - Acc" -> "S - Acc").
    m = re.search(
        r"Produit (.{3,150}?)\s+(?:Un Compartiment de|Société de gestion\s*:|[A-Z]{2}[A-Z0-9]{9}\d\s*-\s*Devise)",
        flat,
    )
    if m:
        name = clean(m.group(1))
        return name, _amundi_share_class(name)
    # FFG-style: "Produit <name> un compartiment de <umbrella> classe <class> - <ISIN>"
    m = re.search(r"Produit\s+(.+?)\s+un compartiment de .+? classe (.+?)\s*-\s*[A-Z]{2}[A-Z0-9]{9}\d", flat)
    if m:
        return clean(m.group(1)), clean(m.group(2))
    # Robeco / La Française: "Produit : <name> (<ISIN>)" or "Produit : <name> Code ISIN"
    m = re.search(r"Produit\s*:\s*(.+?)\s*(?:\([A-Z]{2}[A-Z0-9]{9}\d\)|Code ISIN)", flat)
    if m:
        return clean(m.group(1)), None
    # Crédit Mutuel AM: the title directly follows the document heading
    m = re.search(r"Document d'informations clés\s+(.+?)\s+OBJECTIF\b", flat)
    if m:
        cm = re.search(r"Code ISIN (Part \S+)\s*:", flat)
        return clean(m.group(1)), clean(cm.group(1)) if cm else None
    return None, None


# Amundi class suffix: up to two short code tokens ("S", "A EUR", "I2")
# then " - Acc"/" - Dist"/" - C"/" - D". UCITS/ETF are part of the fund name.
AMUNDI_CLASS = re.compile(
    r"\s((?:(?!ETF\b|UCITS\b)[A-Z][A-Z0-9]{0,3}\s){0,2}-\s(?:Acc|Dist|Inc|C|D))$"
)


def _amundi_share_class(name):
    m = AMUNDI_CLASS.search(name)
    return clean(m.group(1).lstrip("- ")) if m else None


def extract_issuer(flat):
    m = re.search(
        r"Initiateur\s*(?:/ Société de gestion)?\s*(?:Nom)?\s*:\s*(.+?)"
        r"(?:\.\s|\s+(?:Code ISIN|Coordonnées|En quoi|L'autorité|Site internet))",
        flat,
    )
    if m:
        return clean(m.group(1))
    m = re.search(r"chargée du contrôle de (.+?) en ce qui concerne", flat)
    if m:
        return clean(m.group(1))
    # iShares: "élaboré par <issuer> (le « Gestionnaire »)"
    m = re.search(r"élaboré par (.{3,100}?) \(le « Gestionnaire »\)", flat)
    if m:
        return clean(m.group(1))
    # Indépendance AM: "Nom de l'initiateur du PRIIP (...) : <issuer> Classe ..."
    m = re.search(r"Nom de l'initiateur[^:]{0,120}:\s*(.{3,100}?)\s+(?:Classe|ISIN|Site)", flat)
    if m:
        return clean(m.group(1))
    # Natixis: "Ce Produit est géré par <issuer>, qui fait partie ..."
    m = re.search(r"(?:Ce Produit|Cet OPCVM|Le Fonds) est géré par (.{3,100}?)(?:,|\s+qui\b|\s+Part\b)", flat)
    return clean(m.group(1)) if m else None


def extract_website(flat):
    m = re.search(r"\b(?:https?://)?www\.[^\s,;)]+", flat)
    if not m:
        # ODDO: "http://am.oddo-bhf.com" (no www.)
        m = re.search(r"\bhttps?://[^\s,;)]+", flat)
    return clean(m.group(0).rstrip(".")) if m else None


def extract_phone(flat):
    m = re.search(
        r"(?:Appelez le(?: n°)?|Téléphonez au|appele[zr] le|par téléphone au)\s*(\(?\+?[0-9][0-9 ()]{6,}\d)",
        flat,
    )
    return clean(m.group(1)) if m else None


def extract_email(flat):
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", flat)
    return clean(m.group(0).rstrip(".")) if m else None


def extract_type(flat):
    return find(
        r"(?:TYPE DE PRODUIT D'INVESTISSEMENT|TYPE|Type(?: de produit)?\s*:?)\s+(.{5,400}?)\s*"
        r"(?=DUREE DE VIE|DURÉE|Durée|Terme|OBJECTIFS|Objectifs|Ce document d'informations|Échéance)",
        flat,
        flags=0,
    )


def extract_term(flat):
    return find(
        r"(?:DUREE DE VIE DE L'OPC|DURÉE|Durée(?: de vie| et modalités)?\s*:?|Terme)\s+(.{5,600}?)\s*"
        r"(?=OBJECTIFS|Objectifs)",
        flat,
        flags=0,
    )


def extract_objective(flat):
    return find(
        r"(?:OBJECTIFS|Objectifs\s*:?)\s+(.*?)\s*(?=" + INTENDED_HEADING + ")",
        flat,
        flags=0,
    )


CUSTODIAN_LABEL = r"(?:Nom du dépositaire|[Dd]épositaire(?: du Produit| de la SICAV| du [Ff]onds| du compartiment)?)"
# The name ends at the next sentence or section: a capitalized stop word,
# or a full stop that isn't part of an initialism ("S.C.A.", "J.P.").
CUSTODIAN_END = (
    r"(?:\s*(?=\s(?:Le|La|Les|Revenus|Autres|Pour|Ce|Cette|Des|Page|Informations|Document|Quels|QUELS|L'utilisation)\s)"
    r"|(?<![\s.][A-Z])\.(?=\s))"
)


def extract_custodian(flat):
    # The labelled form ("Dépositaire du Produit : X") wins over prose like
    # "le Dépositaire est tenu par la loi ..." (Natixis).
    m = re.search(CUSTODIAN_LABEL + r"\s*:\s*(.+?)" + CUSTODIAN_END, flat) or re.search(
        CUSTODIAN_LABEL + r"\s*est\s*(.+?)" + CUSTODIAN_END, flat
    )
    return clean(m.group(1)) if m else None


def extract_index(flat):
    m = re.search(r"indice de référence\s*(?:est\s*)?:?\s*(?:l[ea]\s+)?([A-Z][^.(,;]+?)\s*(?:\(|\.|,|;)", flat)
    return clean(m.group(1)) if m else None


def extract_currency(flat):
    m = re.search(r"devise de (?:la classe d'actions|la part|référence)[^.]{0,30}?\b([A-Z]{3})\b", flat)
    if m:
        return m.group(1)
    # iShares: "Vos actions seront libellées en euro"
    m = re.search(r"libellées en (euro|dollar américain|dollar US|livre sterling|franc suisse)", flat)
    if m:
        return CURRENCY_NAME_FR[m.group(1)]
    example = extract_example_investment(flat)
    return example["currency"] if example else None


def extract_sfdr_article(flat):
    m = re.search(r"[Aa]rticle\s*(6|8|9)\b\s*(?:du|de la|selon le)\s*(?:[Rr]èglement|SFDR)(?!\s*ELTIF)", flat)
    return f"Article {m.group(1)}" if m else None


def extract_distribution_policy(flat):
    if re.search(
        r"(?:distribuables|dividendes|résultats)\s*:\s*Distribution|(?:parts?|classe|actions?) de distribution",
        flat,
    ):
        return "Distributing"
    if re.search(r"capitalis", flat, re.I):
        return "Accumulating"
    return None


def extract_is_ucits(flat):
    head = flat[:4000]
    if re.search(r"\bFIA\b|FIVG|ELTIF|Fonds Commun de Placement à Risques|\bFCPR\b|\bFCPI\b", head):
        return False
    if re.search(r"OPCVM|UCITS|valeurs mobilières|Partie I de la loi", head):
        return True
    return None


def extract_intended_for(flat):
    body = find(
        r"(?:" + INTENDED_HEADING + r")\s*:?\s*(.*?)"
        r"(?=INFORMATIONS PRATIQUES|Informations pratiques|Autres informations|Quels sont les risques|QUELS SONT)",
        flat,
        flags=0,
    ) or ""
    # "de détail" also covers Natixis' "investisseurs institutionnels et de détail"
    is_retail = bool(re.search(
        r"de détail|particuliers|tous (?:les )?(?:types d')?investisseurs|tout souscripteur|connaissance", body, re.I
    ))
    is_professional = bool(re.search(r"professionnels|institutionnels|contreparties éligibles", body, re.I))
    if is_retail and is_professional:
        return "Retail/Professional"
    if is_retail:
        return "Retail"
    if is_professional:
        return "Professional"
    return None


def extract_sri(flat):
    m = re.search(r"(?:classe de risque|indicateur de risque|niveau|catégorie)\s*(\d)\s*sur\s*7", flat)
    return int(m.group(1)) if m else None


def extract_rhp_years(flat):
    m = re.search(
        r"(?:[Pp]ériode (?:de détention|d'investissement)|[Dd]urée de placement) recommandée"
        r"\s*(?:\(RHP\))?\s*:?\s*(?:supérieure? à\s*)?(\d+)\s*[Aa]ns?\b",
        flat,
    )
    return int(m.group(1)) if m else None


def extract_example_investment(flat):
    # "Investissement : 10 000 €", "Exemple d'investissement : EUR 10.000"
    for m in re.finditer(r"(?:Exemple d'investissement|Investissement)\s*:?\s*", flat):
        money = _find_money(flat[m.end():m.end() + 30])
        if money and money[0][0].start() == 0:
            return _money(money[0][1], money[0][2])
    return None


def extract_scenarios(flat):
    starts = []
    for key, label in SCENARIO_LABELS:
        m = re.search(label + SCENARIO_ROW_START, flat)
        starts.append((m.start(), m.end(), key) if m else None)
    found = sorted(s for s in starts if s)

    scenarios = {key: None for key, _ in SCENARIO_LABELS}
    for i, (_, end, key) in enumerate(found):
        stop = found[i + 1][0] if i + 1 < len(found) else len(flat)
        chunk = flat[end:stop]
        em = re.search(SCENARIO_END, chunk)
        if em:
            chunk = chunk[:em.start()]
        # drop the "Si vous sortez après N an(s)" headers, whose year
        # counts would otherwise read as amounts
        chunk = re.sub(r"Si vous sortez après \d+ [Aa]ns?(?: \(période de détention recommandée\))?", "", chunk)
        amounts = [(amount, symbol) for _, amount, symbol in _find_money(chunk)]
        pcts = re.findall(PCT_FR, chunk)
        if not amounts:
            continue

        def point(amount, pct):
            return {**_money(*amount), "return_pct": parse_pct(pct) if pct is not None else None}

        scenarios[key] = {
            "1y": point(amounts[0], pcts[0] if pcts else None),
            "rhp": point(amounts[-1], pcts[-1] if pcts else None),
        }
    return scenarios


def extract_total_costs(flat):
    # "Incidences des coûts annuels*" (ODDO), "Impact sur les coûts annuels
    # (*)" (iShares), "Incidence des coûts annuels**" (Amundi / CPR)
    impact = (
        r"(?:Incidences? des co[ûu]ts|Impact sur les co[ûu]ts)(?: annuels)?\s*\(?\*{0,2}\)?\s*"
        r"(.*?)(?=\(?\*|Elle montre|Cela illustre|Ceci illustre)"
    )
    m = re.search(r"Co[ûu]ts? totaux?\s+(.*?)" + impact, flat) or re.search(r"Co[ûu]t total\s+(.*?)" + impact, flat)
    if not m:
        return None, None, None, None
    amounts = [(amount, symbol) for _, amount, symbol in _find_money(m.group(1))]
    pcts = re.findall(PCT_FR, m.group(2))
    if not amounts or not pcts:
        return None, None, None, None
    return (
        _money(*amounts[0]),
        _money(*amounts[-1]),
        parse_pct(pcts[0]),
        parse_pct(pcts[-1]),
    )


def extract_cost_example_investment(flat):
    m = re.search(
        r"(?:Investissement|Exemple d'investissement)\s*:?\s*(?:" + MONEY_FR + "|" + MONEY_FR_PREFIX + r")\s*(?:Sc[ée]narios\s*)?Si vous sortez",
        flat,
    )
    if m:
        if m.group(1) is not None:
            return _money(m.group(1), m.group(2))
        return _money(m.group(4), m.group(3))
    m = re.search(AMOUNT + r"\s*(euros|EUR|€)\s*(?:sont|est)\s*investis?", flat)
    if m:
        # abs(): Indépendance lists it as "; -10 000 EUR sont investis"
        return {"value": abs(parse_amount(m.group(1))), "currency": "EUR"}
    # Robeco: currency code before the amount ("EUR 10,000 est investi")
    m = re.search(r"\b(EUR|USD|GBP|CHF)\s" + AMOUNT + r"\s*(?:sont|est)\s*investis?", flat)
    if m:
        return {"value": parse_amount(m.group(2)), "currency": m.group(1)}
    return None


def extract_cost_breakdown(flat):
    m = re.search(r"COMPOSITION DES CO[UÛ]TS|Composition des co[ûu]ts", flat)
    section = flat[m.end():] if m else flat
    em = re.search(COST_SECTION_END, section)
    if em:
        section = section[:em.start()]

    boundaries = []
    for key, label in COST_CATEGORIES:
        bm = re.search(label, section)
        if bm:
            boundaries.append((bm.start(), bm.end(), key))
    boundaries.sort()

    breakdown = {key: {"description": None, "pct": None, "amount": None} for key, _ in COST_CATEGORIES}
    for i, (_, end, key) in enumerate(boundaries):
        chunk_end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(section)
        chunk = section[end:chunk_end]
        for boilerplate in BOILERPLATE:
            chunk = re.sub(boilerplate, "", chunk)
        chunk = re.sub(r"\s+", " ", chunk).strip()

        pct_m = re.search(PCT_FR, chunk)
        amount_ms = _find_money(chunk)
        amount = _money(amount_ms[-1][1], amount_ms[-1][2]) if amount_ms else None
        description = chunk[:amount_ms[-1][0].start()] if amount_ms else chunk
        description = re.sub(r"\b[Jj]usqu'à\s*$", "", description.strip())
        pct = parse_pct(pct_m.group(1)) if pct_m else None
        # "Néant" (Natixis) in the amount column means nothing is charged
        nil = amount is None and re.search(r"\bNéant\s*$", description)
        if nil:
            description = description[:nil.start()]
            amount = {"value": 0.0, "currency": None}
            pct = 0.0 if pct is None else pct

        breakdown[key] = {
            "description": clean(description),
            "pct": pct,
            "amount": amount,
        }

    # "Néant" rows carry no currency of their own: take the table's
    currency = next((v["amount"]["currency"] for v in breakdown.values() if v["amount"] and v["amount"]["currency"]), None)
    for v in breakdown.values():
        if v["amount"] and v["amount"]["currency"] is None:
            v["amount"]["currency"] = currency

    performance_desc = breakdown["performance_fees"]["description"] or ""
    performance_fees_yn = (
        not bool(re.search(r"\bAucune commission|ne comporte pas de commission|pas de commission", performance_desc, re.I))
        if performance_desc
        else None
    )
    return breakdown, performance_fees_yn
