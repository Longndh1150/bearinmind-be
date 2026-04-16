from __future__ import annotations

from scripts.seed.units import SEED_UNITS, _ensure_contact_name


def test_seed_units_has_expected_codes():
    expected_codes = {"DN1", "DN2", "DN3", "HU", "HN1", "HN2", "HN3", "HCM", "JP", "AI"}
    actual_codes = {u["code"] for u in SEED_UNITS}
    assert actual_codes == expected_codes


def test_seed_units_have_rich_experts_and_case_studies():
    for unit in SEED_UNITS:
        experts = unit.get("experts", [])
        case_studies = unit.get("case_studies", [])
        assert 5 <= len(experts) <= 10
        assert 2 <= len(case_studies) <= 5


def test_seed_units_have_non_empty_contact_name():
    for unit in SEED_UNITS:
        assert _ensure_contact_name(unit).strip()


def test_contact_name_fallback_when_missing():
    unit = {"code": "DNX", "name": "Demo Unit", "contact_name": None}
    assert _ensure_contact_name(unit) == "DNX Lead"
