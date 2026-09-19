# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime

import pytest

import attr


class TestTransformHook:
    """
    Tests for `attrs(tranform_value_serializer=func)`
    """

    def test_hook_applied(self):
        """
        The transform hook is applied to all attributes.  Types can be missing,
        explicitly set, or annotated.
        """
        results = []

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            results[:] = [(a.name, a.type) for a in attribs]
            return attribs

        @attr.s(field_transformer=hook)
        class C:
            x = attr.ib()
            y = attr.ib(type=int)
            z: float = attr.ib()

        assert [("x", None), ("y", int), ("z", float)] == results

    def test_hook_applied_auto_attrib(self):
        """
        The transform hook is applied to all attributes and type annotations
        are detected.
        """
        results = []

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            results[:] = [(a.name, a.type) for a in attribs]
            return attribs

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int
            y: str = attr.ib()

        assert [("x", int), ("y", str)] == results

    def test_hook_applied_modify_attrib(self):
        """
        The transform hook can modify attributes.
        """

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            return [a.evolve(converter=a.type) for a in attribs]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int = attr.ib(converter=int)
            y: float

        c = C(x="3", y="3.14")

        assert C(x=3, y=3.14) == c

    def test_hook_remove_field(self):
        """
        It is possible to remove fields via the hook.
        """

        def hook(cls, attribs):
            attr.resolve_types(cls, attribs=attribs)
            return [a for a in attribs if a.type is not int]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int
            y: float

        assert {"y": 2.7} == attr.asdict(C(2.7))

    def test_hook_add_field(self):
        """
        It is possible to add fields via the hook.
        """

        def hook(cls, attribs):
            a1 = attribs[0]
            a2 = a1.evolve(name="new")
            return [a1, a2]

        @attr.s(auto_attribs=True, field_transformer=hook)
        class C:
            x: int

        assert {"x": 1, "new": 2} == attr.asdict(C(1, 2))

    def test_hook_override_alias(self):
        """
        It is possible to set field alias via hook
        """

        def use_dataclass_names(cls, attribs):
            return [a.evolve(alias=a.name) for a in attribs]

        @attr.s(auto_attribs=True, field_transformer=use_dataclass_names)
        class NameCase:
            public: int
            _private: int
            __dunder__: int

        assert NameCase(public=1, _private=2, __dunder__=3) == NameCase(
            1, 2, 3
        )

    def test_hook_reorder_fields(self):
        """
        It is possible to reorder fields via the hook.
        """

        def hook(cls, attribs):
            return sorted(attribs, key=lambda x: x.metadata["field_order"])

        @attr.s(field_transformer=hook)
        class C:
            x: int = attr.ib(metadata={"field_order": 1})
            y: int = attr.ib(metadata={"field_order": 0})

        assert {"x": 0, "y": 1} == attr.asdict(C(1, 0))

    def test_hook_reorder_fields_before_order_check(self):
        """
        It is possible to reorder fields via the hook before order-based errors are raised.

        Regression test for #1147.
        """

        def hook(cls, attribs):
            return sorted(attribs, key=lambda x: x.metadata["field_order"])

        @attr.s(field_transformer=hook)
        class C:
            x: int = attr.ib(metadata={"field_order": 1}, default=0)
            y: int = attr.ib(metadata={"field_order": 0})

        assert {"x": 0, "y": 1} == attr.asdict(C(1))

    def test_hook_conflicting_defaults_after_reorder(self):
        """
        Raises `ValueError` if attributes with defaults are followed by
        mandatory attributes after the hook reorders fields.

        Regression test for #1147.
        """

        def hook(cls, attribs):
            return sorted(attribs, key=lambda x: x.metadata["field_order"])

        with pytest.raises(ValueError) as e:

            @attr.s(field_transformer=hook)
            class C:
                x: int = attr.ib(metadata={"field_order": 1})
                y: int = attr.ib(metadata={"field_order": 0}, default=0)

        assert (
            "No mandatory attributes allowed after an attribute with a "
            "default value or factory.  Attribute in question: Attribute"
            "(name='x', default=NOTHING, validator=None, repr=True, "
            "eq=True, eq_key=None, order=True, order_key=None, "
            "hash=None, init=True, "
            "metadata=mappingproxy({'field_order': 1}), type='int', converter=None, "
            "kw_only=False, inherited=False, on_setattr=None, alias='x', "
            "alias_type=<AliasType.DEFAULT: 'default'>)",
        ) == e.value.args

    def test_hook_sees_resolved_default_alias(self):
        """
        The attributes passed to the field_transformer already carry the
        resolved default alias and an alias_type distinguishing it from
        explicit aliases.
        """
        seen = []

        def hook(cls, attribs):
            seen[:] = [(a.name, a.alias, a.alias_type) for a in attribs]
            return attribs

        @attr.s(field_transformer=hook)
        class C:
            public = attr.ib()
            _private = attr.ib()
            explicit = attr.ib(alias="explicit_name")
            _same = attr.ib(alias="_same")

        assert seen == [
            ("public", "public", attr.AliasType.DEFAULT),
            ("_private", "private", attr.AliasType.DEFAULT),
            ("explicit", "explicit_name", attr.AliasType.EXPLICIT),
            ("_same", "_same", attr.AliasType.EXPLICIT),
        ]

    def test_hook_rename_auto_alias_follows(self):
        """
        Renaming a field with a default alias via evolve() makes the alias
        follow the new name.
        """

        def hook(cls, attribs):
            return [
                a.evolve(name="_renamed") if a.name == "_private" else a
                for a in attribs
            ]

        @attr.s(field_transformer=hook)
        class C:
            _private = attr.ib()

        a = attr.fields(C)[0]
        assert a.name == "_renamed"
        assert a.alias == "renamed"
        assert a.alias_type is attr.AliasType.DEFAULT

        assert C(renamed=1)._renamed == 1

    def test_hook_rename_keeps_explicit_alias(self):
        """
        Renaming a field whose alias was explicitly provided leaves the alias
        pointing at the explicit name instead of the old/new field name.
        """

        def hook(cls, attribs):
            return [
                a.evolve(name="_new_name") if a.name == "_old" else a
                for a in attribs
            ]

        @attr.s(field_transformer=hook)
        class C:
            _old = attr.ib(alias="kept_alias")

        a = attr.fields(C)[0]
        assert a.name == "_new_name"
        assert a.alias == "kept_alias"
        assert a.alias_type is attr.AliasType.EXPLICIT

        assert C(kept_alias=1)._new_name == 1

    def test_hook_add_field_gets_default_alias(self):
        """
        A brand-new field added by the transformer without an alias gets the
        default private-name alias after the transformer is done.
        """

        def hook(cls, attribs):
            added = attribs[0].evolve(name="_added", alias=None)
            return [*attribs, added]

        @attr.s(field_transformer=hook)
        class C:
            x = attr.ib()

        fields = attr.fields(C)
        assert [a.name for a in fields] == ["x", "_added"]
        added = fields[1]
        assert added.alias == "added"
        assert added.alias_type is attr.AliasType.DEFAULT

        assert C(x=1, added=2)._added == 2

    def test_hook_add_handbuilt_field_gets_default_alias(self):
        """
        Even a hand-instantiated Attribute with alias=None added by the
        transformer receives a resolved alias and alias_type.
        """

        def hook(cls, attribs):
            new = attr.Attribute(
                name="_new",
                default=7,
                validator=None,
                repr=True,
                cmp=None,
                hash=None,
                init=True,
                inherited=False,
            )
            return [*attribs, new]

        @attr.s(field_transformer=hook)
        class C:
            x = attr.ib()

        added = attr.fields(C)[1]
        assert added.alias == "new"
        assert added.alias_type is attr.AliasType.DEFAULT
        assert C(1)._new == 7

    def test_hook_alias_type_consistent_in_fields(self):
        """
        The alias_type recorded for each field is consistent with the
        generated __init__ signature.
        """
        import inspect

        def hook(cls, attribs):
            def resolve(a):
                if a.alias_type is attr.AliasType.EXPLICIT:
                    return a
                return a.evolve(alias=a.name)

            return [resolve(a) for a in attribs]

        @attr.s(field_transformer=hook)
        class C:
            _private = attr.ib()
            explicit = attr.ib(alias="explicit_name")

        params = list(inspect.signature(C.__init__).parameters)[1:]
        assert params == ["_private", "explicit_name"]

        fields = attr.fields(C)
        assert fields[0].alias == "_private"
        assert fields[0].alias_type is attr.AliasType.EXPLICIT
        assert fields[1].alias == "explicit_name"
        assert fields[1].alias_type is attr.AliasType.EXPLICIT

    def test_hook_with_inheritance(self):
        """
        The hook receives all fields from base classes.
        """

        def hook(cls, attribs):
            assert ["x", "y"] == [a.name for a in attribs]
            # Remove Base' "x"
            return attribs[1:]

        @attr.s(auto_attribs=True)
        class Base:
            x: int

        @attr.s(auto_attribs=True, field_transformer=hook)
        class Sub(Base):
            y: int

        assert {"y": 2} == attr.asdict(Sub(2))

    def test_attrs_attrclass(self):
        """
        The list of attrs returned by a field_transformer is converted to
        "AttrsClass" again.

        Regression test for #821.
        """

        @attr.s(auto_attribs=True, field_transformer=lambda c, a: list(a))
        class C:
            x: int

        fields_type = type(attr.fields(C))
        assert "CAttributes" == fields_type.__name__
        assert issubclass(fields_type, tuple)

    def test_hook_generator(self):
        """
        field_transfromers can be a generators.

        Regression test for #1416.
        """

        def hook(cls, attribs):
            yield from attribs

        @attr.s(auto_attribs=True, field_transformer=hook)
        class Base:
            x: int

        assert ["x"] == [a.name for a in attr.fields(Base)]


class TestAsDictHook:
    def test_asdict(self):
        """
        asdict() calls the hooks in attrs classes and in other datastructures
        like lists or dicts.
        """

        def hook(inst, a, v):
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        @attr.dataclass
        class Child:
            x: datetime
            y: list[datetime]

        @attr.dataclass
        class Parent:
            a: Child
            b: list[Child]
            c: dict[str, Child]
            d: dict[str, datetime]

        inst = Parent(
            a=Child(1, [datetime(2020, 7, 1)]),
            b=[Child(2, [datetime(2020, 7, 2)])],
            c={"spam": Child(3, [datetime(2020, 7, 3)])},
            d={"eggs": datetime(2020, 7, 4)},
        )

        result = attr.asdict(inst, value_serializer=hook)
        assert {
            "a": {"x": 1, "y": ["2020-07-01T00:00:00"]},
            "b": [{"x": 2, "y": ["2020-07-02T00:00:00"]}],
            "c": {"spam": {"x": 3, "y": ["2020-07-03T00:00:00"]}},
            "d": {"eggs": "2020-07-04T00:00:00"},
        } == result

    def test_asdict_calls(self):
        """
        The correct instances and attribute names are passed to the hook.
        """
        calls = []

        def hook(inst, a, v):
            calls.append((inst, a.name if a else a, v))
            return v

        @attr.dataclass
        class Child:
            x: int

        @attr.dataclass
        class Parent:
            a: Child
            b: list[Child]
            c: dict[str, Child]

        inst = Parent(a=Child(1), b=[Child(2)], c={"spam": Child(3)})

        attr.asdict(inst, value_serializer=hook)
        assert [
            (inst, "a", inst.a),
            (inst.a, "x", inst.a.x),
            (inst, "b", inst.b),
            (inst.b[0], "x", inst.b[0].x),
            (inst, "c", inst.c),
            (None, None, "spam"),
            (inst.c["spam"], "x", inst.c["spam"].x),
        ] == calls
