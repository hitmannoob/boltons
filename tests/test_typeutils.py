import copy
import pickle

from boltons.typeutils import make_sentinel, get_all_subclasses

NOT_SET = make_sentinel('not_set', var_name='NOT_SET')

def test_sentinel_falsiness():
    assert not NOT_SET


def test_sentinel_pickle():
    assert pickle.dumps(NOT_SET)

def test_sentinel_copy():
    test = make_sentinel('test')
    assert test is copy.copy(test)
    assert test is copy.deepcopy(test)


def test_get_all_subclasses_metaclass():
    class Meta(type):
        pass

    class SubMeta(Meta):
        pass

    assert get_all_subclasses(Meta) == [SubMeta]
    assert get_all_subclasses(SubMeta) == []


def test_sentinel_repr_and_names():
    unnamed = make_sentinel('TEST')
    assert repr(unnamed) == "Sentinel('TEST')"
    assert unnamed.name == 'TEST'
    assert unnamed.var_name is None
    assert repr(NOT_SET) == 'NOT_SET'
    assert NOT_SET.var_name == 'NOT_SET'


def test_sentinel_identity_and_type_uniqueness():
    first = make_sentinel('TEST')
    second = make_sentinel('TEST')
    assert first is not second
    assert first != second
    assert type(first) is not type(second)


def test_sentinel_var_name_requires_module_scope():
    import pytest

    with pytest.raises(ValueError):
        exec(
            "from boltons.typeutils import make_sentinel\n"
            "make_sentinel('X', var_name='X')",
            {'__name__': 'boltons_module_that_does_not_exist'},
        )


def test_issubclass_matches_and_swallows_bad_args():
    from boltons.typeutils import issubclass

    class Base:
        pass

    class Child(Base):
        pass

    assert issubclass(Child, Base) is True
    assert issubclass(Base, Child) is False
    assert issubclass(Child, object) is True
    assert issubclass('hi', 'friend') is False
    assert issubclass(1, Base) is False


def test_get_all_subclasses_diamond_yields_unique_types():
    class Root:
        pass

    class Left(Root):
        pass

    class Right(Root):
        pass

    class Bottom(Left, Right):
        pass

    found = get_all_subclasses(Root)
    assert set(found) == {Left, Right, Bottom}
    assert len(found) == len(set(found))


def test_get_all_subclasses_rejects_non_types():
    import pytest

    with pytest.raises(TypeError):
        get_all_subclasses('not a type')
    with pytest.raises(TypeError):
        get_all_subclasses(42)


def test_classproperty_binds_to_class():
    from boltons.typeutils import classproperty

    class Thing:
        @classproperty
        def label(cls):
            return cls.__name__

    assert Thing.label == 'Thing'
    assert Thing().label == 'Thing'
