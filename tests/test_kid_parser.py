"""Regression tests against 4 real-world PRIIPs KID templates.

Every value asserted here was hand-verified against the raw PDF text during
development (see project history) -- these guard against regressions when a
5th issuer's template needs new fallback patterns added to kid_parser.fields.
"""

from pathlib import Path

from kid_parser import KidDocument, parse_kid, parse_kids

FIXTURES = Path(__file__).parent / "fixtures"


def _scenario_point(scenario, key):
    point = getattr(scenario, key)
    return (point.value, point.currency, point.return_pct)


def test_ishares_core_msci_world():
    kid = parse_kid(FIXTURES / "PRP_DE_en_IE00B4L5Y983_YES_2026-09-03.pdf")

    assert kid.isin == "IE00B4L5Y983"
    assert kid.product_name == "iShares Core MSCI World UCITS ETF"
    assert kid.share_class == "USD Accu"
    assert kid.issuer == "BlackRock Asset Management Ireland Limited"
    assert kid.website == "www.blackrock.com"
    assert kid.phone == "+49 89427295800"
    assert kid.email == "info@ishares.co.uk"
    assert kid.currency == "USD"
    assert kid.index == "MSCI World Index"  # "reflects the return of the MSCI World Index"
    assert kid.sfdr_article is None
    assert kid.distribution_policy == "Accumulating"
    assert kid.intended_for == "Retail"
    assert kid.sri == 4
    assert kid.rhp_years == 5
    assert kid.example_investment_amount.value == 10000.0
    assert kid.example_investment_amount.currency == "USD"
    assert kid.scenario_time_frame.short == "1 year"
    assert kid.scenario_time_frame.recommended == "5 years"

    assert _scenario_point(kid.scenarios["stress"], "one_year") == (7490.0, "USD", -25.1)
    assert _scenario_point(kid.scenarios["stress"], "rhp") == (3850.0, "USD", -17.4)
    assert _scenario_point(kid.scenarios["unfavourable"], "one_year") == (8050.0, "USD", -19.5)
    assert _scenario_point(kid.scenarios["unfavourable"], "rhp") == (11960.0, "USD", 3.7)
    assert _scenario_point(kid.scenarios["moderate"], "one_year") == (11550.0, "USD", 15.5)
    assert _scenario_point(kid.scenarios["moderate"], "rhp") == (17800.0, "USD", 12.2)
    assert _scenario_point(kid.scenarios["favourable"], "one_year") == (15420.0, "USD", 54.2)
    assert _scenario_point(kid.scenarios["favourable"], "rhp") == (21200.0, "USD", 16.2)

    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_1y.currency) == (20.0, "USD")
    assert (cost.total_cost_rhp.value, cost.total_cost_rhp.currency) == (180.0, "USD")
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (0.2, 0.2)
    assert cost.breakdown.entry_costs.amount is None
    assert cost.breakdown.exit_costs.amount is None
    assert cost.breakdown.management_fees.pct == 0.2
    assert (cost.breakdown.management_fees.amount.value, cost.breakdown.management_fees.amount.currency) == (20.0, "USD")
    assert cost.breakdown.transaction_costs.pct == 0.0
    assert (cost.breakdown.transaction_costs.amount.value, cost.breakdown.transaction_costs.amount.currency) == (0.0, "USD")
    assert cost.performance_fees_yn is False


def test_ishares_msci_emu_paris_aligned():
    kid = parse_kid(FIXTURES / "PRP_DE_en_IE00BL6K8D99_YES_2026-04-09.pdf")

    assert kid.isin == "IE00BL6K8D99"
    assert kid.product_name == "iShares MSCI EMU Paris-Aligned Climate UCITS ETF"
    assert kid.share_class == "EUR Accu"
    assert kid.currency == "EUR"
    assert kid.sfdr_article is None
    assert kid.sri == 4
    assert kid.rhp_years == 5

    assert _scenario_point(kid.scenarios["stress"], "one_year") == (7890.0, "EUR", -21.1)
    assert _scenario_point(kid.scenarios["stress"], "rhp") == (4090.0, "EUR", -16.4)
    assert _scenario_point(kid.scenarios["unfavourable"], "one_year") == (8100.0, "EUR", -19.0)
    assert _scenario_point(kid.scenarios["unfavourable"], "rhp") == (9780.0, "EUR", -0.5)
    assert _scenario_point(kid.scenarios["moderate"], "one_year") == (10980.0, "EUR", 9.8)
    assert _scenario_point(kid.scenarios["moderate"], "rhp") == (13940.0, "EUR", 6.9)
    assert _scenario_point(kid.scenarios["favourable"], "one_year") == (14240.0, "EUR", 42.4)
    assert _scenario_point(kid.scenarios["favourable"], "rhp") == (18170.0, "EUR", 12.7)

    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (18.0, 123.0)
    assert cost.breakdown.management_fees.pct == 0.15
    assert cost.breakdown.transaction_costs.pct == 0.03
    assert cost.performance_fees_yn is False


def test_amundi_emerging_markets_esg():
    kid = parse_kid(FIXTURES / "PRP_DE_en_LU2109787049_YES_2026-06-15.pdf")

    assert kid.isin == "LU2109787049"
    assert kid.product_name == "Amundi MSCI Emerging Markets ESG Broad Transition UCITS ETF Acc"
    # no quoted "Share Class": taken from the name suffix, as in French Amundi KIDs
    assert kid.share_class == "Acc"
    assert kid.issuer == "Amundi Luxembourg S.A"
    assert kid.currency == "USD"
    assert kid.sfdr_article == "Article 8"
    assert kid.distribution_policy == "Accumulating"
    # "Intended retail investor" is mandatory boilerplate; this template's
    # body text never actually names an audience.
    assert kid.intended_for is None
    assert kid.sri == 4
    assert kid.rhp_years == 5

    assert _scenario_point(kid.scenarios["stress"], "one_year") == (4030.0, "USD", -59.7)
    assert _scenario_point(kid.scenarios["stress"], "rhp") == (3340.0, "USD", -19.7)
    assert _scenario_point(kid.scenarios["favourable"], "one_year") == (15720.0, "USD", 57.2)
    assert _scenario_point(kid.scenarios["favourable"], "rhp") == (18030.0, "USD", 12.5)

    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (38.0, 223.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (0.4, 0.4)
    assert cost.breakdown.entry_costs.amount.value == 0.0
    assert cost.breakdown.management_fees.pct == 0.18
    assert cost.breakdown.transaction_costs.amount.value == 20.33
    assert cost.performance_fees_yn is False


def test_lg_clean_water():
    kid = parse_kid(FIXTURES / "PRP_DE_en_IE00BK5BC891_YES_2025-05-19_ADCX.pdf")

    assert kid.isin == "IE00BK5BC891"
    assert kid.product_name == "L&G Clean Water UCITS ETF"
    assert kid.share_class == "USD Accumulating ETF"
    assert kid.issuer == "LGIM Managers (Europe) Limited"
    assert kid.phone == "+44 (0) 203 124 3180"
    assert kid.currency == "USD"
    assert kid.index == "Solactive Clean Water Index NTR"
    assert kid.distribution_policy == "Accumulating"
    assert kid.intended_for is None  # body text names no audience, only the mandatory heading does
    assert kid.sri == 5
    assert kid.rhp_years == 5  # from "recommended holding period of 5 years", not the usual phrasing
    assert kid.example_investment_amount.value == 10000.0  # decimal "10,000.00" handled

    # "Stress scenario*" ordering (word before asterisk), unlike the other 3 templates
    assert _scenario_point(kid.scenarios["stress"], "one_year") == (4570.0, "USD", -54.3)
    assert _scenario_point(kid.scenarios["favourable"], "rhp") == (25300.0, "USD", 20.4)

    cost = kid.cost_section
    # "Impact on return (RIY) per year" wording, not "Annual cost Impact"
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (58.0, 533.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (0.6, 0.7)
    assert cost.breakdown.management_fees.pct == 0.49
    assert cost.breakdown.transaction_costs.pct == 0.09
    # "Performance fees and carried interest" label - suffix must not leak into description
    assert cost.breakdown.performance_fees.description == "0.00% There is no performance fee for this product"
    assert cost.performance_fees_yn is False


def test_parse_kids_over_fixtures_dir():
    kids = parse_kids(FIXTURES)
    assert len(kids) == 4
    assert {kid.isin for kid in kids} == {
        "IE00B4L5Y983", "IE00BL6K8D99", "LU2109787049", "IE00BK5BC891",
    }


def test_json_round_trip():
    kid = parse_kid(FIXTURES / "PRP_DE_en_IE00BL6K8D99_YES_2026-04-09.pdf")
    reloaded = KidDocument.from_json(kid.to_json())
    assert reloaded.to_dict() == kid.to_dict()


# --- French-language KIDs --------------------------------------------------
# One golden test per distinct French template (Crédit Mutuel AM OPCVM and
# FIA, Robeco, FFG/Waystone, La Française, Eiffel IG, iShares, Amundi, CPR,
# ODDO BHF, Indépendance AM, Société Générale IS, Natixis), plus a sweep over
# every fixture for the fields a portfolio tracker actually consumes.

FR_FIXTURES = FIXTURES / "fr"


def _fr(isin_and_date):
    return parse_kid(FR_FIXTURES / f"KID_fr_{isin_and_date}.pdf")


def _scenario(kid, name):
    s = kid.scenarios[name]
    return (s.one_year.value, s.one_year.return_pct, s.rhp.value, s.rhp.return_pct)


def test_fr_cm_am_opcvm_human_care():
    kid = _fr("FR0013041654_2026-03-02")

    assert kid.language == "fr"
    assert kid.isin == "FR0013041654"
    assert kid.production_date == "2026-03-02"
    assert kid.product_name == "CM-AM HUMAN CARE"  # soft hyphen "CM ­AM" repaired
    assert kid.share_class == "Part RC"
    assert kid.issuer == "CREDIT MUTUEL ASSET MANAGEMENT"
    assert kid.custodian == "BANQUE FEDERATIVE DU CREDIT MUTUEL"
    assert kid.type == "OPCVM sous forme de fonds commun de placement (FCP)"
    assert kid.is_ucits is True
    assert kid.distribution_policy == "Accumulating"
    assert kid.currency == "EUR"
    assert kid.sri == 4
    assert kid.rhp_years == 5
    assert kid.sfdr_article is None  # not stated in this KID
    assert (kid.example_investment_amount.value, kid.example_investment_amount.currency) == (10000.0, "EUR")

    # "­79,7 %": soft-hyphen minus, comma decimal, space-grouped "2 030 €"
    assert _scenario(kid, "stress") == (2030.0, -79.7, 2270.0, -25.7)
    assert _scenario(kid, "unfavourable") == (7050.0, -29.5, 7390.0, -5.9)
    assert _scenario(kid, "moderate") == (9940.0, -0.6, 10070.0, 1.0)
    assert _scenario(kid, "favourable") == (13520.0, 35.2, 13610.0, 6.4)

    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (411.0, 1336.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (4.2, 2.6)
    b = cost.breakdown
    assert (b.entry_costs.pct, b.entry_costs.amount.value) == (2.0, 200.0)
    assert b.exit_costs.amount.value == 0.0
    assert (b.management_fees.pct, b.management_fees.amount.value) == (1.9, 186.0)
    assert (b.transaction_costs.pct, b.transaction_costs.amount.value) == (0.31, 25.0)
    assert cost.performance_fees_yn is False


def test_fr_cm_am_fia_is_not_ucits():
    kid = _fr("FR0014001TX4_2026-09-01")

    assert kid.product_name == "CM-AM SOLIDAIRE TEMPERE ISR"
    assert kid.is_ucits is False  # "Ce FIA", FIVG
    assert kid.sri == 2
    assert (kid.cost_section.breakdown.management_fees.pct, kid.cost_section.breakdown.transaction_costs.pct) == (0.78, 0.03)


def test_fr_robeco_english_style_numbers():
    kid = _fr("LU2145461757_2026-07-16")

    assert kid.production_date == "2026-07-16"  # "Date de publication 16/7/2026"
    assert kid.product_name == "Robeco Smart Energy D EUR"
    assert kid.issuer == "Robeco Institutional Asset Management B.V"
    assert kid.custodian == "J.P. Morgan SE"
    assert kid.sfdr_article == "Article 9"
    assert kid.index == "MSCI All Country World Index"  # "Indice de référence: MSCI ..."
    assert kid.sri == 5
    assert kid.rhp_years == 5  # "5 Ans"
    # "3,100 EUR" is three thousand one hundred, "-69.0%" a dot decimal
    assert _scenario(kid, "stress") == (3100.0, -69.0, 2370.0, -25.0)
    cost = kid.cost_section
    assert (cost.example_cost_amount.value, cost.example_cost_amount.currency) == (10000.0, "EUR")
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (692.0, 3111.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (6.9, 3.4)
    assert (cost.breakdown.entry_costs.pct, cost.breakdown.entry_costs.amount.value) == (5.0, 500.0)
    assert cost.breakdown.management_fees.pct == 1.72
    assert cost.breakdown.transaction_costs.pct == 0.2


def test_fr_ffg_three_holding_periods():
    kid = _fr("LU2612532759_2026-07-11")

    assert kid.product_name == "FFG - BLI Global Impact Equities"
    assert kid.share_class == "R Acc"
    assert kid.issuer == "Waystone Management Company (Lux) S.A"
    assert kid.custodian == "Banque de Luxembourg"
    assert kid.rhp_years == 10
    # 1 / 5 / 10-year columns: rhp is the last one, "5.410 EUR" dot-grouped
    assert _scenario(kid, "stress") == (5410.0, -45.9, 3610.0, -9.7)
    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (511.0, 4554.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (5.1, 2.4)
    assert (cost.breakdown.management_fees.pct, cost.breakdown.transaction_costs.pct) == (1.8, 0.3)


def test_fr_la_francaise_alternate_labels():
    kid = _fr("LU1744646933_2025-08-06")

    assert kid.sri == 4  # "catégorisé ce produit au niveau 4 sur 7"
    assert kid.rhp_years == 5
    assert kid.sfdr_article == "Article 9"
    assert kid.index == "MSCI All Country World Index"
    # "Scénario de tensions" row label, "Coût total", "Frais de transaction"
    assert _scenario(kid, "stress") == (4660.0, -53.4, 3530.0, -18.8)
    assert _scenario(kid, "favourable") == (14510.0, 45.1, 17050.0, 11.3)
    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (544.0, 2178.0)
    assert (cost.breakdown.management_fees.pct, cost.breakdown.transaction_costs.pct) == (2.03, 0.49)
    assert cost.performance_fees_yn is False


def test_fr_eiffel_eltif_with_performance_fee():
    kid = _fr("FR001400OLI0_2026-06-05")

    assert (kid.product_name, kid.share_class) == ("EIFFEL INFRASTRUCTURES VERTES", "Part A")
    assert kid.issuer == "EIFFEL INVESTMENT GROUP"
    assert kid.custodian == "Société Générale"
    assert kid.is_ucits is False  # ELTIF / FCPR
    assert kid.sri == 3
    # amounts and returns interleaved per column ("8 586 EUR -14,14 % 8 117 EUR -4,09 %")
    assert _scenario(kid, "moderate") == (10767.0, 7.67, 14712.0, 8.03)
    cost = kid.cost_section
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (2.02, 2.18)
    # "15 % TTC max de la performance annuelle" rate, real amount 0 EUR
    assert (cost.breakdown.performance_fees.pct, cost.breakdown.performance_fees.amount.value) == (15.0, 0.0)
    assert cost.performance_fees_yn is True


def test_fr_ishares_matches_english_kid_of_same_fund():
    fr = _fr("IE00BL6K8D99_2026-04-09")
    en = parse_kid(FIXTURES / "PRP_DE_en_IE00BL6K8D99_YES_2026-04-09.pdf")

    # "Produit <name> (le « Fonds ») <class> (la « Catégorie d'actions »)"
    for field in ("isin", "product_name", "share_class", "issuer", "currency", "sri", "rhp_years", "production_date", "index"):
        assert getattr(fr, field) == getattr(en, field), field
    assert fr.custodian == "The Bank of New York Mellon SA/NV, succursale de Dublin"
    # "Tension*" / "Défavorable**" row labels, "7.890 EUR" dot thousands
    for name in ("stress", "unfavourable", "moderate", "favourable"):
        assert fr.scenarios[name].to_dict() == en.scenarios[name].to_dict(), name
    cost = fr.cost_section
    # "Impact sur les coûts annuels (*)" wording
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (18.0, 123.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (0.2, 0.2)
    # "Frais de gestion et autres coûts administratifs ou frais d'exploitation";
    # the quoted « Coûts de transaction » inside that row is not the label
    assert (cost.breakdown.management_fees.pct, cost.breakdown.management_fees.amount.value) == (0.15, 15.0)
    assert (cost.breakdown.transaction_costs.pct, cost.breakdown.transaction_costs.amount.value) == (0.03, 3.0)
    assert cost.performance_fees_yn is False


def test_fr_amundi_etf_currency_before_amount():
    kid = _fr("FR001400ZGO4_2026-07-13")

    assert kid.product_name == "Amundi PEA Emergent (MSCI Emerging) ESG Transition UCITS ETF S - Acc"
    # the name keeps its class suffix, which is also reported on its own
    assert kid.share_class == "S - Acc"
    assert kid.issuer == "Amundi Asset Management"
    assert kid.custodian == "CACEIS Bank"
    assert kid.is_ucits is True
    # "répliquer le plus fidèlement possible la performance de l'indice ..."
    assert kid.index == "MSCI EM ex-Egypt ESG Broad CTB Select Index"
    # the "Classification AMF (...) : Actions ..." line that follows is not part of the term
    for amundi in (kid, _fr("FR001400AED5_2026-07-17")):
        assert amundi.term == (
            "La durée du produit est de 99 ans. La Société de gestion peut dissoudre le produit "
            "par liquidation ou fusion avec un autre produit conformément aux exigences légales"
        )
    # "€4 380 €3 350": each amount paired with its own leading symbol
    assert _scenario(kid, "stress") == (4380.0, -56.2, 3350.0, -19.6)
    assert _scenario(kid, "favourable") == (14900.0, 49.0, 15200.0, 8.7)
    cost = kid.cost_section
    assert (cost.example_cost_amount.value, cost.example_cost_amount.currency) == (10000.0, "EUR")
    # "Coûts totaux €30 €180 Incidence des coûts annuels** 0,3% 0,3%"
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (30.0, 180.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (0.3, 0.3)
    assert (cost.breakdown.management_fees.pct, cost.breakdown.management_fees.amount.value) == (0.3, 30.0)
    assert cost.performance_fees_yn is False


def test_fr_cpr_amundi_group_template():
    kid = _fr("LU1902443420_2026-09-01")

    assert (kid.product_name, kid.share_class) == ("CPR Invest - Climate Action - A EUR - Acc", "A EUR - Acc")
    assert kid.issuer == "CPR Asset Management"
    assert kid.production_date == "2026-09-01"  # "Ce document a été publié le 01/09/2026"
    assert kid.phone == "+33 153157000"  # "appeler le"
    assert kid.custodian == "CACEIS Bank, succursale de Luxembourg"
    assert kid.sfdr_article == "Article 8"
    # only an unnamed "Indice de référence a posteriori"; the MSCI ACWI is the performance-fee hurdle
    assert kid.index is None
    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (714.0, 2183.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (7.3, 3.6)
    # the management-fee row no longer leaks into exit costs
    assert cost.breakdown.exit_costs.pct is None
    assert (cost.breakdown.management_fees.pct, cost.breakdown.management_fees.amount.value) == (1.95, 185.63)
    # "15,00 % annuel de performance au-delà ..." rate, real amount 1,05 EUR
    assert (cost.breakdown.performance_fees.pct, cost.breakdown.performance_fees.amount.value) == (15.0, 1.05)
    assert cost.performance_fees_yn is True


def test_fr_oddo_bhf():
    kid = _fr("FR0011606268_2026-08-27")

    assert (kid.product_name, kid.share_class) == ("ODDO BHF Active Small Cap", "CR-EUR")
    assert kid.issuer == "ODDO BHF Asset Management SAS"
    assert kid.website == "http://am.oddo-bhf.com"
    assert kid.custodian == "ODDO BHF SCA"
    assert kid.sfdr_article == "Article 8"  # "classifié article 8 selon le Règlement (UE) 2019/2088"
    assert kid.index == "MSCI Europe Small Caps"  # "surperformer l'indice « MSCI Europe Small Caps »"
    # singular "Tension" row label
    assert _scenario(kid, "stress") == (3940.0, -60.6, 3300.0, -19.9)
    cost = kid.cost_section
    # "Incidences des coûts annuels*"
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (645.0, 1906.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (6.6, 3.5)
    assert (cost.breakdown.management_fees.pct, cost.breakdown.management_fees.amount.value) == (2.13, 204.0)
    # the 20 % fee rate, and the actual EUR amount (based on the last 5 years)
    assert (cost.breakdown.performance_fees.pct, cost.breakdown.performance_fees.amount.value) == (20.0, 3.0)
    assert cost.performance_fees_yn is True


def test_fr_independance_am():
    kid = _fr("LU1832174962_2026-07-22")

    assert (kid.product_name, kid.share_class) == ("Europe Small", "A (C)")
    assert kid.issuer == "Indépendance AM S.A.S"
    assert kid.production_date == "2026-07-22"  # "22.07.2026"
    assert kid.phone == "(+33) 1 40 76 02 85"
    assert kid.sri == 4  # "dans l'indicateur de risque 4 sur 7"
    assert kid.currency == "EUR"
    assert kid.index is None  # the Stoxx index only sets the performance-fee hurdle
    # "EUR 4 340 EUR 3 850"
    assert _scenario(kid, "stress") == (4340.0, -56.6, 3850.0, -17.38)
    assert _scenario(kid, "favourable") == (15910.0, 59.1, 25240.0, 20.34)
    cost = kid.cost_section
    assert cost.example_cost_amount.value == 10000.0  # not the "-10 000" list dash
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (598.0, 4424.0)
    assert (cost.cost_impact_pct_1y, cost.cost_impact_pct_rhp) == (5.9, 5.0)
    assert (cost.breakdown.entry_costs.pct, cost.breakdown.entry_costs.amount.value) == (2.0, 200.0)
    # "Commissions liées aux résultats (et commission d'intéressement) 1,52%
    # Description : 10% lorsque la performance ...": pct is the 10 % fee
    # rate, not the 1.52 % impact; amount is the real EUR amount
    assert (cost.breakdown.performance_fees.pct, cost.breakdown.performance_fees.amount.value) == (10.0, 152.0)
    assert cost.performance_fees_yn is True


def test_fr_societe_generale_bourso_fivg():
    kid = _fr("FR001400RWK6_2026-07-23")

    assert kid.product_name == "Bourso Monde"
    assert kid.issuer == "Société Générale Investment Solutions (France)"
    assert kid.custodian == "Société Générale"
    assert kid.is_ucits is False  # FIVG
    # the iShares master's "reflète le rendement total net de l'indice ..."
    assert kid.index == "MSCI World Index"
    # SG's own feeder: "répliquer, le plus fidèlement possible, la performance de l'Indice MSCI EUROPE"
    assert _fr("FR001400RWJ8_2026-07-23").index == "MSCI EUROPE"
    assert kid.intended_for == "Retail"  # "Type d'investisseurs visés : ... tout souscripteur"
    # "Scénario de tension", dot decimals "-61.40%"
    assert _scenario(kid, "stress") == (3860.0, -61.4, 3940.0, -17.0)
    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (56.0, 500.0)
    # the "10 000 EUR sont investis" footnote is not a performance-fee amount
    assert cost.breakdown.performance_fees.amount.value == 0.0
    assert cost.performance_fees_yn is False


def test_fr_natixis_mirova():
    kid = _fr("LU1951200481_2026-04-13")

    assert (kid.product_name, kid.share_class) == ("Mirova Thematic AI & Robotics", "R/A (EUR)")
    assert kid.issuer == "Natixis Investment Managers International"
    assert kid.production_date == "2026-04-13"  # "à jour au 13 avril 2026"
    assert kid.custodian == "Brown Brothers Harriman (Luxembourg) S.C.A"
    assert kid.intended_for == "Retail/Professional"  # "institutionnels et de détail"
    assert kid.sri == 5
    assert kid.index is None  # the MSCI ACWI is only an indicative comparison
    # "Défavorable (*)" row labels
    assert _scenario(kid, "stress") == (3200.0, -68.0, 2140.0, -26.6)
    assert _scenario(kid, "unfavourable") == (6990.0, -30.1, 9970.0, -0.1)
    cost = kid.cost_section
    assert (cost.total_cost_1y.value, cost.total_cost_rhp.value) == (614.0, 1794.0)
    # "Néant" means nothing is charged: 0, in the table's currency
    exit_costs = cost.breakdown.exit_costs
    assert (exit_costs.pct, exit_costs.amount.value, exit_costs.amount.currency) == (0.0, 0.0, "EUR")
    assert exit_costs.description == "Nous ne facturons pas de coût de sortie"
    # ... and the market-timing "2 %" note after the table is not a performance fee
    assert (cost.breakdown.performance_fees.pct, cost.breakdown.performance_fees.amount.value) == (0.0, 0.0)
    assert cost.performance_fees_yn is False


def test_fr_every_fixture_has_the_core_fields():
    kids = parse_kids(FR_FIXTURES)
    assert len(kids) == 23
    for kid in kids:
        assert kid.language == "fr", kid.source_file
        for field in ("isin", "product_name", "issuer", "production_date", "sri", "rhp_years", "currency", "distribution_policy", "supervisor"):
            assert getattr(kid, field) is not None, (kid.source_file, field)
        assert kid.cost_section.total_cost_1y is not None, kid.source_file
        assert kid.cost_section.breakdown.management_fees.pct is not None, kid.source_file
        assert all(kid.scenarios[name] is not None for name in ("stress", "unfavourable", "moderate", "favourable")), kid.source_file


def test_english_kids_carry_language_and_production_date():
    kid = parse_kid(FIXTURES / "PRP_DE_en_IE00B4L5Y983_YES_2026-09-03.pdf")
    assert kid.language == "en"
    assert kid.production_date == "2026-09-03"
    assert kid.is_ucits is True
    assert kid.supervisor == "CBI"


def test_supervisor_is_the_fund_domicile_regulator():
    # LU funds run by French managers: the KID names the AMF (manager's
    # regulator), but the fund itself is supervised by the CSSF
    for isin_and_date in ("LU1902443420_2026-09-01", "LU1951200481_2026-04-13", "LU1832174962_2026-07-22"):
        assert _fr(isin_and_date).supervisor == "CSSF", isin_and_date
    assert _fr("FR001400RWK6_2026-07-23").supervisor == "AMF"
    # "Banque centrale d'Irlande (la « BCI »)" -> same acronym as in English
    assert _fr("IE00BL6K8D99_2026-04-09").supervisor == "CBI"
    assert parse_kid(FIXTURES / "PRP_DE_en_LU2109787049_YES_2026-06-15.pdf").supervisor == "CSSF"


def test_english_active_benchmark_wordings():
    # no active-fund English fixture yet: synthetic sentences
    from kid_parser.fields import extract_index

    assert extract_index("The Fund aims to outperform the MSCI Europe Index (the Benchmark) over 5 years.") == "MSCI Europe Index"
    assert extract_index("Benchmark: MSCI World Index. The fund is actively managed.") == "MSCI World Index"
    assert extract_index("The fund is actively managed with reference to the S&P 500 Index (the benchmark).") == "S&P 500 Index"
    assert extract_index("Benchmark: None. The fund is actively managed.") is None
    assert extract_index("It seeks to outperform its benchmark over the long term.") is None
    # a tracked index wins over a stated benchmark
    assert extract_index("Benchmark: MSCI ACWI. It aims to track the performance of the FTSE 100 Index (the Index).") == "FTSE 100 Index"
