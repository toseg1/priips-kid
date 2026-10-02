"""Top-level parse_kid / parse_kids entry points."""

import os
from pathlib import Path

from . import fields, fields_fr
from .models import CostBreakdown, CostLineItem, CostSection, KidDocument, Money, Scenario, ScenarioPoint, ScenarioTimeFrame
from .text import detect_language, extract_pdf_text, normalize_flat


def _money(data):
    return Money(**data) if data else None


def _cost_line_item(data):
    return CostLineItem(
        description=data["description"],
        pct=data["pct"],
        amount=_money(data["amount"]),
    )


def _scenario(data):
    if data is None:
        return None
    one_year = data["1y"]
    rhp = data["rhp"]
    return Scenario(
        one_year=ScenarioPoint(**one_year) if one_year else None,
        rhp=ScenarioPoint(**rhp) if rhp else None,
    )


def parse_kid(pdf_path) -> KidDocument:
    pdf_path = str(pdf_path)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    raw_text = extract_pdf_text(pdf_path)
    flat = normalize_flat(raw_text)
    language = detect_language(flat)
    filename_fields = fields.parse_filename(stem)

    if language == "fr":
        return _assemble(pdf_path, flat, language, fields_fr, filename_fields, {
            "product_and_class": fields_fr.extract_product_and_class(flat),
            "production_date": fields_fr.extract_production_date(flat),
        })
    return _assemble(pdf_path, flat, language, fields, filename_fields, {
        "product_and_class": fields.extract_product_and_class(fields.extract_product_section(flat)),
        "production_date": fields.extract_production_date(flat, filename_fields.get("date")),
    })


def _assemble(pdf_path, flat, language, f, filename_fields, specific) -> KidDocument:
    """Builds the KidDocument from one language's extractor module `f`
    (kid_parser.fields or kid_parser.fields_fr -- same function names),
    plus the few values whose extraction signature differs by language."""
    isin = f.extract_isin(flat, filename_fields.get("isin"))
    product_name, share_class = specific["product_and_class"]
    rhp_years = f.extract_rhp_years(flat)

    total_1y, total_rhp, impact_1y, impact_rhp = f.extract_total_costs(flat)
    breakdown, performance_fees_yn = f.extract_cost_breakdown(flat)

    cost_breakdown = CostBreakdown(
        entry_costs=_cost_line_item(breakdown["entry_costs"]),
        exit_costs=_cost_line_item(breakdown["exit_costs"]),
        management_fees=_cost_line_item(breakdown["management_fees"]),
        transaction_costs=_cost_line_item(breakdown["transaction_costs"]),
        performance_fees=_cost_line_item(breakdown["performance_fees"]),
    )

    scenarios_raw = f.extract_scenarios(flat)
    scenario_time_frame_raw = fields.extract_scenario_time_frame(rhp_years)

    return KidDocument(
        source_file=pdf_path,
        isin=isin,
        product_name=product_name,
        share_class=share_class,
        issuer=f.extract_issuer(flat),
        website=f.extract_website(flat),
        phone=f.extract_phone(flat),
        email=f.extract_email(flat),
        type=f.extract_type(flat),
        term=f.extract_term(flat),
        objective=f.extract_objective(flat),
        custodian=f.extract_custodian(flat),
        index=f.extract_index(flat),
        currency=f.extract_currency(flat),
        sfdr_article=f.extract_sfdr_article(flat),
        distribution_policy=f.extract_distribution_policy(flat),
        intended_for=f.extract_intended_for(flat),
        sri=f.extract_sri(flat),
        rhp_years=rhp_years,
        example_investment_amount=_money(f.extract_example_investment(flat)),
        scenario_time_frame=ScenarioTimeFrame(**scenario_time_frame_raw),
        scenarios={name: _scenario(value) for name, value in scenarios_raw.items()},
        cost_section=CostSection(
            example_cost_amount=_money(f.extract_cost_example_investment(flat)),
            total_cost_1y=_money(total_1y),
            total_cost_rhp=_money(total_rhp),
            cost_impact_pct_1y=impact_1y,
            cost_impact_pct_rhp=impact_rhp,
            breakdown=cost_breakdown,
            performance_fees_yn=performance_fees_yn,
        ),
        language=language,
        production_date=specific["production_date"],
        is_ucits=f.extract_is_ucits(flat),
        supervisor=fields.extract_supervisor(isin),
    )


def _iter_pdf_paths(paths):
    if isinstance(paths, (str, Path)):
        path = Path(paths)
        if path.is_dir():
            yield from sorted(path.glob("*.pdf"))
        else:
            yield path
        return
    for item in paths:
        yield from _iter_pdf_paths(item)


def parse_kids(paths) -> list:
    """Parse a directory of PDFs, a single PDF, or an iterable of either."""
    return [parse_kid(p) for p in _iter_pdf_paths(paths)]
