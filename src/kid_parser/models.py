"""Dataclass model for a parsed PRIIPs KID, with optional JSON (de)serialization.

JSON is not produced as a side effect of parsing -- `parse_kid()` returns a
`KidDocument` and nothing is written to disk. `to_json`/`from_json` are there
for callers who *want* to persist or reload a document; both are plain,
opt-in method calls.
"""

import dataclasses
import json
from pathlib import Path
from typing import Optional


def _opt(cls, data):
    return cls.from_dict(data) if data is not None else None


@dataclasses.dataclass
class Money:
    value: float
    currency: Optional[str]

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(value=data["value"], currency=data.get("currency"))


@dataclasses.dataclass
class ScenarioPoint:
    value: Optional[float]
    currency: Optional[str]
    return_pct: Optional[float]

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            value=data.get("value"),
            currency=data.get("currency"),
            return_pct=data.get("return_pct"),
        )


@dataclasses.dataclass
class Scenario:
    one_year: Optional[ScenarioPoint]
    rhp: Optional[ScenarioPoint]

    def to_dict(self):
        return {
            "1y": self.one_year.to_dict() if self.one_year else None,
            "rhp": self.rhp.to_dict() if self.rhp else None,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            one_year=_opt(ScenarioPoint, data.get("1y")),
            rhp=_opt(ScenarioPoint, data.get("rhp")),
        )


@dataclasses.dataclass
class CostLineItem:
    description: Optional[str]
    pct: Optional[float]
    amount: Optional[Money]

    def to_dict(self):
        return {
            "description": self.description,
            "pct": self.pct,
            "amount": self.amount.to_dict() if self.amount else None,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            description=data.get("description"),
            pct=data.get("pct"),
            amount=_opt(Money, data.get("amount")),
        )


@dataclasses.dataclass
class CostBreakdown:
    entry_costs: CostLineItem
    exit_costs: CostLineItem
    management_fees: CostLineItem
    transaction_costs: CostLineItem
    performance_fees: CostLineItem

    def to_dict(self):
        return {
            "entry_costs": self.entry_costs.to_dict(),
            "exit_costs": self.exit_costs.to_dict(),
            "management_fees": self.management_fees.to_dict(),
            "transaction_costs": self.transaction_costs.to_dict(),
            "performance_fees": self.performance_fees.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            entry_costs=CostLineItem.from_dict(data["entry_costs"]),
            exit_costs=CostLineItem.from_dict(data["exit_costs"]),
            management_fees=CostLineItem.from_dict(data["management_fees"]),
            transaction_costs=CostLineItem.from_dict(data["transaction_costs"]),
            performance_fees=CostLineItem.from_dict(data["performance_fees"]),
        )


@dataclasses.dataclass
class CostSection:
    example_cost_amount: Optional[Money]
    total_cost_1y: Optional[Money]
    total_cost_rhp: Optional[Money]
    cost_impact_pct_1y: Optional[float]
    cost_impact_pct_rhp: Optional[float]
    breakdown: CostBreakdown
    performance_fees_yn: Optional[bool]

    def to_dict(self):
        return {
            "example_cost_amount": self.example_cost_amount.to_dict() if self.example_cost_amount else None,
            "total_cost_1y": self.total_cost_1y.to_dict() if self.total_cost_1y else None,
            "total_cost_rhp": self.total_cost_rhp.to_dict() if self.total_cost_rhp else None,
            "cost_impact_pct_1y": self.cost_impact_pct_1y,
            "cost_impact_pct_rhp": self.cost_impact_pct_rhp,
            "breakdown": self.breakdown.to_dict(),
            "performance_fees_yn": self.performance_fees_yn,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            example_cost_amount=_opt(Money, data.get("example_cost_amount")),
            total_cost_1y=_opt(Money, data.get("total_cost_1y")),
            total_cost_rhp=_opt(Money, data.get("total_cost_rhp")),
            cost_impact_pct_1y=data.get("cost_impact_pct_1y"),
            cost_impact_pct_rhp=data.get("cost_impact_pct_rhp"),
            breakdown=CostBreakdown.from_dict(data["breakdown"]),
            performance_fees_yn=data.get("performance_fees_yn"),
        )


@dataclasses.dataclass
class ScenarioTimeFrame:
    short: str
    recommended: Optional[str]

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(short=data["short"], recommended=data.get("recommended"))


@dataclasses.dataclass
class KidDocument:
    source_file: str
    isin: Optional[str]
    product_name: Optional[str]
    share_class: Optional[str]
    issuer: Optional[str]
    website: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    type: Optional[str]
    term: Optional[str]
    objective: Optional[str]
    custodian: Optional[str]
    index: Optional[str]
    currency: Optional[str]
    sfdr_article: Optional[str]
    distribution_policy: Optional[str]
    intended_for: Optional[str]
    sri: Optional[int]
    rhp_years: Optional[int]
    example_investment_amount: Optional[Money]
    scenario_time_frame: ScenarioTimeFrame
    scenarios: dict  # name -> Optional[Scenario]
    cost_section: CostSection
    language: Optional[str] = None  # "en" | "fr"
    production_date: Optional[str] = None  # ISO date the KID was produced
    is_ucits: Optional[bool] = None
    supervisor: Optional[str] = None  # fund domicile regulator: "AMF", "CSSF", "CBI", ...

    def to_dict(self):
        return {
            "source_file": self.source_file,
            "isin": self.isin,
            "product_name": self.product_name,
            "share_class": self.share_class,
            "issuer": self.issuer,
            "website": self.website,
            "phone": self.phone,
            "email": self.email,
            "type": self.type,
            "term": self.term,
            "objective": self.objective,
            "custodian": self.custodian,
            "index": self.index,
            "currency": self.currency,
            "sfdr_article": self.sfdr_article,
            "distribution_policy": self.distribution_policy,
            "intended_for": self.intended_for,
            "sri": self.sri,
            "rhp_years": self.rhp_years,
            "example_investment_amount": (
                self.example_investment_amount.to_dict() if self.example_investment_amount else None
            ),
            "scenario_time_frame": self.scenario_time_frame.to_dict(),
            "scenarios": {
                name: (scenario.to_dict() if scenario else None)
                for name, scenario in self.scenarios.items()
            },
            "cost_section": self.cost_section.to_dict(),
            "language": self.language,
            "production_date": self.production_date,
            "is_ucits": self.is_ucits,
            "supervisor": self.supervisor,
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data):
        return cls(
            source_file=data["source_file"],
            isin=data.get("isin"),
            product_name=data.get("product_name"),
            share_class=data.get("share_class"),
            issuer=data.get("issuer"),
            website=data.get("website"),
            phone=data.get("phone"),
            email=data.get("email"),
            type=data.get("type"),
            term=data.get("term"),
            objective=data.get("objective"),
            custodian=data.get("custodian"),
            index=data.get("index"),
            currency=data.get("currency"),
            sfdr_article=data.get("sfdr_article"),
            distribution_policy=data.get("distribution_policy"),
            intended_for=data.get("intended_for"),
            sri=data.get("sri"),
            rhp_years=data.get("rhp_years"),
            example_investment_amount=_opt(Money, data.get("example_investment_amount")),
            scenario_time_frame=ScenarioTimeFrame.from_dict(data["scenario_time_frame"]),
            scenarios={
                name: (_opt(Scenario, value))
                for name, value in data.get("scenarios", {}).items()
            },
            cost_section=CostSection.from_dict(data["cost_section"]),
            language=data.get("language"),
            production_date=data.get("production_date"),
            is_ucits=data.get("is_ucits"),
            supervisor=data.get("supervisor"),
        )

    @classmethod
    def from_json(cls, source):
        """Load from a JSON string, or from a file when `source` is a path."""
        # A JSON document always starts with "{"; only anything else is
        # treated as a path (Path.is_file() on a long JSON string raises
        # "File name too long" on macOS instead of returning False).
        if isinstance(source, Path) or (isinstance(source, str) and not source.lstrip().startswith("{")):
            text = Path(source).read_text(encoding="utf-8")
        else:
            text = source
        return cls.from_dict(json.loads(text))
