from __future__ import annotations

from app.modules.units.models import UomDataSpecification, UomRegistryEntry
from app.modules.units.registry import UomRegistryService, build_registry_indexes


def test_load_seed_entries_returns_deterministic_rows() -> None:
    service = UomRegistryService()

    entries = service.load_seed_entries()

    assert entries
    assert [entry.cd_id for entry in entries] == sorted(entry.cd_id for entry in entries)
    assert all(entry.data_specification.symbol for entry in entries)


def test_build_registry_indexes_groups_by_cd_specific_and_symbol() -> None:
    entries = [
        UomRegistryEntry(
            cd_id="urn:unit:one",
            data_specification=UomDataSpecification(
                preferred_name={"en": "metre"},
                symbol="m",
                specific_unit_id="MTR",
                definition={"en": "length"},
                preferred_name_quantity={"en": "length"},
                quantity_id="LEN",
                classification_system="UNECE Rec 20",
                classification_system_version="2024",
            ),
            source="seed",
        ),
        UomRegistryEntry(
            cd_id="urn:unit:two",
            data_specification=UomDataSpecification(
                preferred_name={"en": "metre-alt"},
                symbol="m",
                specific_unit_id="MTR_ALT",
                definition={"en": "length alt"},
                preferred_name_quantity={"en": "length"},
                quantity_id="LEN",
                classification_system="UNECE Rec 20",
                classification_system_version="2024",
            ),
            source="seed",
        ),
    ]

    by_cd_id, by_specific_unit_id, by_symbol = build_registry_indexes(entries)

    assert set(by_cd_id.keys()) == {"urn:unit:one", "urn:unit:two"}
    assert by_specific_unit_id["MTR"][0].cd_id == "urn:unit:one"
    assert [entry.cd_id for entry in by_symbol["m"]] == ["urn:unit:one", "urn:unit:two"]
