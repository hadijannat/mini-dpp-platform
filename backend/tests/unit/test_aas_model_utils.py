"""Unit tests for shared AAS model utilities."""

from basyx.aas import model

from app.modules.aas.model_utils import (
    clear_parent,
    clone_identifiable,
    enum_to_str,
    iterable_attr,
    lang_string_set_to_dict,
    walk_submodel_deep,
)

# ---------------------------------------------------------------------------
# enum_to_str
# ---------------------------------------------------------------------------


class TestEnumToStr:
    def test_none(self) -> None:
        assert enum_to_str(None) is None

    def test_basyx_enum(self) -> None:
        # BaSyx enums have integer values; enum_to_str returns str(value)
        result = enum_to_str(model.ModellingKind.TEMPLATE)
        assert result is not None
        assert result == str(model.ModellingKind.TEMPLATE.value)

    def test_type_object_returns_class_name_only(self) -> None:
        assert enum_to_str(model.Property) == "Property"
        assert enum_to_str(model.SubmodelElementCollection) == "SubmodelElementCollection"

    def test_string_passthrough(self) -> None:
        assert enum_to_str("hello") == "hello"


# ---------------------------------------------------------------------------
# lang_string_set_to_dict
# ---------------------------------------------------------------------------


class TestLangStringSetToDict:
    def test_none(self) -> None:
        assert lang_string_set_to_dict(None) == {}

    def test_empty_set(self) -> None:
        assert lang_string_set_to_dict([]) == {}

    def test_basyx_lang_string_set(self) -> None:
        lss = model.LangStringSet({"en": "Hello", "de": "Hallo"})
        result = lang_string_set_to_dict(lss)
        assert result["en"] == "Hello"
        assert result["de"] == "Hallo"

    def test_plain_string(self) -> None:
        assert lang_string_set_to_dict("raw") == {"und": "raw"}


# ---------------------------------------------------------------------------
# iterable_attr
# ---------------------------------------------------------------------------


class TestIterableAttr:
    def test_missing_attr(self) -> None:
        assert iterable_attr(object(), "nonexistent") == []

    def test_list_attr(self) -> None:
        obj = type("Obj", (), {"items": [3, 1, 2]})()
        result = iterable_attr(obj, "items")
        assert result == [3, 1, 2]  # list returned as-is, not sorted

    def test_first_matching_name_wins(self) -> None:
        obj = type("Obj", (), {"a": None, "b": [42]})()
        result = iterable_attr(obj, "a", "b")
        assert result == [42]


# ---------------------------------------------------------------------------
# clear_parent
# ---------------------------------------------------------------------------


class TestClearParent:
    def test_clears_simple_element(self) -> None:
        prop = model.Property(id_short="P1", value_type=model.datatypes.String)
        # BaSyx sets parent when added to a namespace; we verify clear_parent resets it
        sm = model.Submodel(id_="urn:sm:cp", id_short="SM", submodel_element=[prop])
        assert prop.parent is sm
        clear_parent(prop)
        assert prop.parent is None

    def test_clears_children_in_collection(self) -> None:
        child = model.Property(id_short="Child", value_type=model.datatypes.String)
        smc = model.SubmodelElementCollection(id_short="SMC", value=[child])
        # child.parent is set to smc by BaSyx
        assert child.parent is smc
        clear_parent(smc)
        assert smc.parent is None
        assert child.parent is None

    def test_clears_entity_statements(self) -> None:
        stmt = model.Property(id_short="Stmt", value_type=model.datatypes.String)
        entity = model.Entity(
            id_short="E1",
            entity_type=model.EntityType.CO_MANAGED_ENTITY,
            statement=[stmt],
        )
        assert stmt.parent is entity
        clear_parent(entity)
        assert entity.parent is None
        assert stmt.parent is None


# ---------------------------------------------------------------------------
# clone_identifiable
# ---------------------------------------------------------------------------


class TestCloneIdentifiable:
    def test_cloned_has_no_parent(self) -> None:
        cd = model.ConceptDescription(id_="urn:cd:1", id_short="CD1")
        cd.parent = object()  # type: ignore[assignment]
        cloned = clone_identifiable(cd)
        assert cloned.parent is None
        assert cloned.id == "urn:cd:1"

    def test_clone_is_independent(self) -> None:
        cd = model.ConceptDescription(id_="urn:cd:2", id_short="CD2")
        cloned = clone_identifiable(cd)
        cloned.id_short = "Modified"
        assert cd.id_short == "CD2"


# ---------------------------------------------------------------------------
# walk_submodel_deep
# ---------------------------------------------------------------------------


class TestWalkSubmodelDeep:
    def test_walks_collection_children(self) -> None:
        p1 = model.Property(id_short="P1", value_type=model.datatypes.String)
        p2 = model.Property(id_short="P2", value_type=model.datatypes.String)
        smc = model.SubmodelElementCollection(id_short="SMC", value=[p1, p2])

        elements = list(walk_submodel_deep(smc))
        id_shorts = [e.id_short for e in elements]
        assert "P1" in id_shorts
        assert "P2" in id_shorts

    def test_walks_entity_statements(self) -> None:
        stmt = model.Property(id_short="Stmt", value_type=model.datatypes.String)
        entity = model.Entity(
            id_short="E1",
            entity_type=model.EntityType.CO_MANAGED_ENTITY,
            statement=[stmt],
        )
        elements = list(walk_submodel_deep(entity))
        assert any(e.id_short == "Stmt" for e in elements)

    def test_walks_nested_structure(self) -> None:
        """Verify deep traversal: Submodel → Collection → Property."""
        inner = model.Property(id_short="Inner", value_type=model.datatypes.String)
        smc = model.SubmodelElementCollection(id_short="SMC", value=[inner])
        sm = model.Submodel(id_="urn:sm:1", id_short="SM", submodel_element=[smc])

        elements = list(walk_submodel_deep(sm))
        id_shorts = [e.id_short for e in elements]
        assert "SMC" in id_shorts
        assert "Inner" in id_shorts

    def test_property_yields_nothing(self) -> None:
        """A leaf element (Property) has no children to yield."""
        prop = model.Property(id_short="Leaf", value_type=model.datatypes.String)
        assert list(walk_submodel_deep(prop)) == []
