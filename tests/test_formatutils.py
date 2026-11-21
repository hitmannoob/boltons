import re
from collections import namedtuple

from boltons.formatutils import (get_format_args,
                                 split_format_str,
                                 tokenize_format_str,
                                 infer_positional_format_args,
                                 DeferredValue as DV)


PFAT = namedtuple("PositionalFormatArgTest", "fstr arg_vals res")

_PFATS = [PFAT('{} {} {}', ('hi', 'hello', 'bye'), "hi hello bye"),
          PFAT('{:d} {}', (1, 2), "1 2"),
          PFAT('{!s} {!r}', ('str', 'repr'), "str 'repr'"),
          PFAT('{[hi]}, {.__name__!r}', ({'hi': 'hi'}, re), "hi, 're'"),
          PFAT('{{joek}} ({} {})', ('so', 'funny'), "{joek} (so funny)")]


def test_pos_infer():
    for i, (tmpl, args, res) in enumerate(_PFATS):
        converted = infer_positional_format_args(tmpl)
        assert converted.format(*args) == res


_TEST_TMPLS = ["example 1: {hello}",
               "example 2: {hello:*10}",
               "example 3: {hello:*{width}}",
               "example 4: {hello!r:{fchar}{width}}, {width}, yes",
               "example 5: {0}, {1:d}, {2:f}, {1}",
               "example 6: {}, {}, {}, {1}"]


def test_get_fstr_args():
    results = []
    for t in _TEST_TMPLS:
        inferred_t = infer_positional_format_args(t)
        res = get_format_args(inferred_t)
        assert res


def test_split_fstr():
    results = []
    for t in _TEST_TMPLS:
        res = split_format_str(t)
        results.append(res)
        assert res


def test_tokenize_format_str():
    results = []
    for t in _TEST_TMPLS:
        res = tokenize_format_str(t)
        results.append(res)
        assert res


def test_deferredvalue():
    def myfunc():
        myfunc.called += 1
        return 123

    myfunc.called = 0

    dv = DV(myfunc)
    assert str(dv) == '123'
    assert myfunc.called == 1
    assert str(dv) == '123'
    assert myfunc.called == 1
    dv.cache_value = False
    assert str(dv) == '123'
    assert myfunc.called == 2
    assert str(dv) == '123'
    assert myfunc.called == 3


def test_construct_format_field_str():
    from boltons.formatutils import construct_format_field_str

    assert construct_format_field_str(None, None, None) == ''
    assert construct_format_field_str('name', '', None) == '{name}'
    assert construct_format_field_str('name', '>10', 'r') == '{name!r:>10}'


def test_get_format_args_exact_types_and_dedup():
    fargs, fkwargs = get_format_args('{0} {0} {name} {name}')
    assert fargs == [(0, str)]
    assert fkwargs == [('name', str)]

    fargs, fkwargs = get_format_args('{1:d} {2:f}')
    assert fargs == [(1, int), (2, float)]
    assert fkwargs == []


def test_get_format_args_rejects_compound_and_anonymous():
    import pytest

    with pytest.raises(ValueError):
        get_format_args('{a.b}')
    with pytest.raises(ValueError):
        get_format_args('{}')


def test_base_format_field_fstr_repr_str():
    from boltons.formatutils import BaseFormatField

    field = BaseFormatField('name')
    assert field.fstr == '{name}'
    assert str(field) == '{name}'
    assert repr(field) == "BaseFormatField('name')"
    assert field.is_positional is False

    field = BaseFormatField('name', '>10')
    assert field.fstr == '{name:>10}'
    assert repr(field) == "BaseFormatField('name', '>10')"

    field = BaseFormatField('name', '>10', 'r')
    assert field.fstr == '{name!r:>10}'
    assert repr(field) == "BaseFormatField('name', '>10', 'r')"

    assert BaseFormatField('0').is_positional is True
    assert BaseFormatField('').is_positional is True


def test_deferredvalue_conversions_and_format():
    dv = DV(lambda: 42)
    assert int(dv) == 42
    assert float(dv) == 42.0
    assert repr(dv) == '42'
    assert dv.__unicode__() == '42'
    assert format(dv, 'd') == '42'

    # str has no 'd' presentation type, so __format__ falls back to the
    # nominal int conversion for that presentation type.
    dv_str = DV(lambda: '7')
    assert format(dv_str, 'd') == '7'
