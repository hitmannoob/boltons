import sys
import types
import warnings

import pytest

from boltons.deprutils import DeprecatableModule, deprecate_module_member


@pytest.fixture
def fake_module():
    name = 'boltons_test_depr_module'
    mod = types.ModuleType(name)
    mod.old_value = 42
    mod.current = lambda: 'ok'
    sys.modules[name] = mod
    try:
        yield name
    finally:
        sys.modules.pop(name, None)


def test_deprecate_module_member_warns_and_returns_value(fake_module):
    deprecate_module_member(fake_module, 'old_value', 'old_value is deprecated')
    mod = sys.modules[fake_module]

    assert isinstance(mod, DeprecatableModule)
    with pytest.warns(DeprecationWarning, match='old_value is deprecated'):
        assert mod.old_value == 42


def test_deprecate_module_member_does_not_warn_for_normal_members(fake_module):
    deprecate_module_member(fake_module, 'old_value', 'old_value is deprecated')
    mod = sys.modules[fake_module]

    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert mod.current() == 'ok'
        assert mod.__name__ == fake_module


def test_deprecate_module_member_reuses_existing_wrapper(fake_module):
    deprecate_module_member(fake_module, 'old_value', 'first message')
    wrapped = sys.modules[fake_module]

    deprecate_module_member(fake_module, 'current', 'second message')

    assert sys.modules[fake_module] is wrapped
    assert wrapped._deprecated_members == {
        'old_value': 'first message',
        'current': 'second message',
    }


def test_deprecatable_module_copies_module_attributes():
    name = 'boltons_test_depr_copy'
    mod = types.ModuleType(name)
    mod.value = 'original'

    wrapped = DeprecatableModule(mod)

    assert wrapped.__name__ == name
    assert wrapped.value == 'original'
    assert wrapped._deprecated_members == {}
