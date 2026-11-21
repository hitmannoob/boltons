from pickle import loads, dumps

import pytest

from boltons.namedutils import namedlist, namedtuple

Point = namedtuple('Point', 'x, y', rename=True)
MutablePoint = namedlist('MutablePoint', 'x, y', rename=True)


def test_namedlist():
    p = MutablePoint(x=10, y=20)

    assert p == [10, 20]
    p[0] = 11
    assert p == [11, 20]
    p.x = 12
    assert p == [12, 20]


def test_namedlist_pickle():
    p = MutablePoint(x=10, y=20)
    assert p == loads(dumps(p))


def test_namedtuple_pickle():
    p = Point(x=10, y=20)
    assert p == loads(dumps(p))


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_empty_field_name_raises_value_error(factory):
    # `all()` is True for the empty string, so an empty name used to pass both
    # ValueError checks and reach `name[0].isdigit()`, raising IndexError.
    with pytest.raises(ValueError):
        factory('Point', ['x', ''])


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_empty_type_name_raises_value_error(factory):
    with pytest.raises(ValueError):
        factory('', ['x', 'y'])


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_invalid_character_still_raises_value_error(factory):
    with pytest.raises(ValueError):
        factory('Point', ['x', 'y-z'])


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_non_identifier_alnum_name(factory):
    # '²' passes str.isalnum() but is not valid in a Python identifier
    with pytest.raises(ValueError):
        factory('T', ['value\u00b2'])
    assert factory('T', ['value\u00b2', 'b'], rename=True)._fields == ('_0', 'b')


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_keyword_field_name_raises_value_error(factory):
    with pytest.raises(ValueError):
        factory('Point', ['class'])


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_leading_digit_field_name_raises_value_error(factory):
    with pytest.raises(ValueError):
        factory('Point', ['1x'])


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_underscore_field_name_raises_value_error(factory):
    with pytest.raises(ValueError):
        factory('Point', ['_x'])


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_duplicate_field_name_raises_value_error(factory):
    with pytest.raises(ValueError):
        factory('Point', ['x', 'x'])


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_verbose_prints_definition(factory, capsys):
    cls = factory('VerbosePoint', ['x', 'y'], verbose=True)
    out = capsys.readouterr().out
    assert 'class VerbosePoint' in out
    assert cls(1, 2)._asdict() == {'x': 1, 'y': 2}


@pytest.mark.parametrize("factory", [namedtuple, namedlist])
def test_survives_unavailable_getframe(factory, monkeypatch):
    from types import SimpleNamespace
    import boltons.namedutils as namedutils

    def _no_frames(*args, **kwargs):
        raise AttributeError('frame introspection unavailable')

    monkeypatch.setattr(namedutils, '_sys', SimpleNamespace(_getframe=_no_frames))
    cls = factory('NoFramePoint', ['x'])
    assert cls(5).x == 5
