"""Unit tests for semantic-registry-driven drop-in expansion."""

from __future__ import annotations

from basyx.aas import model

from app.modules.templates.dropin_resolver import TemplateDropInResolver

TARGET_SEMANTIC = "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"
SOURCE_SEMANTIC = "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/ContactInformation"


def _ref(iri: str) -> model.Reference:
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, iri),))


def _source_submodel() -> model.Submodel:
    return model.Submodel(
        id_="urn:test:source",
        id_short="ContactInformations",
        submodel_element=[
            model.SubmodelElementCollection(
                id_short="ContactInformation",
                semantic_id=_ref(SOURCE_SEMANTIC),
                value=[
                    model.Property(
                        id_short="Street", value_type=model.datatypes.String, value=None
                    ),
                    model.Property(
                        id_short="CityTown", value_type=model.datatypes.String, value=None
                    ),
                ],
            )
        ],
    )


def _target_submodel() -> model.Submodel:
    return model.Submodel(
        id_="urn:test:target",
        id_short="Nameplate",
        submodel_element=[
            model.SubmodelElementCollection(
                id_short="AddressInformation",
                semantic_id=_ref(TARGET_SEMANTIC),
                value=[],
            )
        ],
    )


def test_dropin_resolver_expands_address_information_children() -> None:
    resolver = TemplateDropInResolver()
    target = _target_submodel()

    resolution = resolver.resolve(
        template_key="digital-nameplate",
        submodel=target,
        source_provider=lambda _: _source_submodel(),
    )

    address = next(iter(target.submodel_element))
    assert isinstance(address, model.SubmodelElementCollection)
    assert len(list(address.value)) == 2
    assert [child.id_short for child in address.value] == ["CityTown", "Street"]

    metadata = resolution[id(address)]
    assert metadata["status"] == "resolved"
    assert metadata["source_template_key"] == "contact-information"


def test_dropin_resolver_reports_unresolved_when_source_is_missing() -> None:
    resolver = TemplateDropInResolver()
    target = _target_submodel()

    resolution = resolver.resolve(
        template_key="digital-nameplate",
        submodel=target,
        source_provider=lambda _: None,
    )

    address = next(iter(target.submodel_element))
    metadata = resolution[id(address)]
    assert metadata["status"] == "unresolved"
    assert metadata["reason"] == "source_template_unavailable"


def test_dropin_resolver_keeps_deterministic_resolution_output() -> None:
    resolver = TemplateDropInResolver()

    target_a = _target_submodel()
    target_b = _target_submodel()

    resolution_a = resolver.resolve(
        template_key="digital-nameplate",
        submodel=target_a,
        source_provider=lambda _: _source_submodel(),
    )
    resolution_b = resolver.resolve(
        template_key="digital-nameplate",
        submodel=target_b,
        source_provider=lambda _: _source_submodel(),
    )

    metadata_a = list(resolution_a.values())[0]
    metadata_b = list(resolution_b.values())[0]
    assert metadata_a == metadata_b


def test_dropin_resolver_respects_registry_template_scope() -> None:
    resolver = TemplateDropInResolver()
    target = _target_submodel()

    resolution = resolver.resolve(
        template_key="technical-data",
        submodel=target,
        source_provider=lambda _: _source_submodel(),
    )

    # Registry binding is scoped to digital-nameplate/carbon-footprint.
    assert resolution == {}
    address = next(iter(target.submodel_element))
    assert isinstance(address, model.SubmodelElementCollection)
    assert len(list(address.value)) == 0
