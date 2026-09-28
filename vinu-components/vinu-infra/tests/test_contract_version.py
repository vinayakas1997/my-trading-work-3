from __future__ import annotations

from pydantic import BaseModel

from vinu_infra.contract_version import contract_version


class _ModelA(BaseModel):
    symbol: str
    limit: int = 10


class _ModelAIdenticalShape(BaseModel):
    symbol: str
    limit: int = 10


class _ModelADifferentField(BaseModel):
    symbol: str
    limit: int = 10
    extra: bool = False


class _ModelADifferentDefault(BaseModel):
    symbol: str
    limit: int = 20


class _ModelADifferentDocstringOnly(BaseModel):
    """This docstring differs but the fields are identical."""
    symbol: str
    limit: int = 10


class TestContractVersion:
    def test_deterministic_for_the_same_model(self) -> None:
        assert contract_version(_ModelA) == contract_version(_ModelA)

    def test_identical_shape_under_a_different_class_name_matches(self) -> None:
        assert contract_version(_ModelA) == contract_version(_ModelAIdenticalShape)

    def test_an_added_field_changes_the_version(self) -> None:
        assert contract_version(_ModelA) != contract_version(_ModelADifferentField)

    def test_a_changed_default_changes_the_version(self) -> None:
        assert contract_version(_ModelA) != contract_version(_ModelADifferentDefault)

    def test_a_docstring_change_alone_does_not_change_the_version(self) -> None:
        assert contract_version(_ModelA) == contract_version(_ModelADifferentDocstringOnly)

    def test_returns_a_short_hex_string(self) -> None:
        version = contract_version(_ModelA)
        assert isinstance(version, str)
        assert len(version) == 12
        int(version, 16)  # raises if not valid hex
