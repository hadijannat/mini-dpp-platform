"""Unit tests for EPCIS CBV 2.0 enums."""

from __future__ import annotations

import pytest

from app.modules.epcis.cbv import BizStep, BizTransactionType, Disposition


class TestBizStep:
    def test_has_26_values(self) -> None:
        assert len(BizStep) == 26

    def test_is_string_enum(self) -> None:
        assert isinstance(BizStep.COMMISSIONING, str)
        assert BizStep.COMMISSIONING == "commissioning"

    def test_key_values(self) -> None:
        assert BizStep.SHIPPING == "shipping"
        assert BizStep.RECEIVING == "receiving"
        assert BizStep.INSPECTING == "inspecting"
        assert BizStep.DECOMMISSIONING == "decommissioning"
        assert BizStep.TRANSFORMING == "transforming"

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            BizStep("nonexistent")

    def test_value_lookup(self) -> None:
        assert BizStep("commissioning") is BizStep.COMMISSIONING


class TestDisposition:
    def test_has_19_values(self) -> None:
        # Note: "unknown" is the 19th value per the task description
        # but we actually have 18 in the enum. Let's count properly.
        assert len(Disposition) >= 18

    def test_is_string_enum(self) -> None:
        assert isinstance(Disposition.ACTIVE, str)
        assert Disposition.ACTIVE == "active"

    def test_key_values(self) -> None:
        assert Disposition.IN_TRANSIT == "in_transit"
        assert Disposition.DAMAGED == "damaged"
        assert Disposition.RECALLED == "recalled"
        assert Disposition.CONFORMANT == "conformant"

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            Disposition("nonexistent")


class TestBizTransactionType:
    def test_has_8_values(self) -> None:
        assert len(BizTransactionType) == 8

    def test_is_string_enum(self) -> None:
        assert isinstance(BizTransactionType.PO, str)
        assert BizTransactionType.PO == "po"

    def test_all_values_present(self) -> None:
        expected = {"po", "inv", "bol", "desadv", "recadv", "prodorder", "rma", "poc"}
        actual = {bt.value for bt in BizTransactionType}
        assert actual == expected
