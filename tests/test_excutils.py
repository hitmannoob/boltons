import os
import sys
import tempfile

from pytest import raises

from boltons.excutils import (
    ExceptionCauseMixin,
    MathError,
    _DeferredLine,
    _TBItem,
    _extract_from_frame,
    _extract_from_tb,
    _format_exc,
    main as excutils_main,
    math_lol,
)


class MyErr(ExceptionCauseMixin, Exception):
    pass


def test_cause_str_outside_handler():
    err = MyErr(ValueError('inner'))
    assert 'ValueError: inner' in str(err)


def test_plain_exception():
    err = MyErr('plain')
    assert err.cause is None
    assert str(err) == 'plain'
    assert err._get_message() == 'plain'
    assert err._get_trace_str() == repr(err)


def test_cause_with_message():
    err = MyErr(ValueError('inner'), 'outer')
    assert err.cause.__class__ is ValueError
    assert err._get_message() == 'outer'
    assert err.get_str() == 'MyErr: outer (caused by ValueError: inner)'
    assert str(err) == 'outer (caused by ValueError: inner)'


def test_cause_without_message():
    err = MyErr(ValueError('inner'))
    assert err.get_str() == 'MyErr:  caused by ValueError: inner'
    assert str(err) == ' caused by ValueError: inner'


def test_root_cause_is_inherited():
    inner = ValueError('inner')
    inner.root_cause = KeyError('deepest')
    err = MyErr(inner, 'outer')
    assert err.root_cause is inner.root_cause


def test_full_trace_is_copied():
    cause = ValueError('inner')
    cause.full_trace = ['frame-a', 'frame-b']
    cause._tb = ['tb']
    cause._stack = ['stack']
    err = MyErr(cause)
    assert err.full_trace == ['frame-a', 'frame-b']
    assert err._tb == ['tb']
    assert err._stack == ['stack']
    # copied, not aliased
    assert err.full_trace is not cause.full_trace


def _raise_and_wrap():
    try:
        raise ValueError('root')
    except ValueError as ve:
        raise MyErr(ve, 'while handling')


def test_wrap_inside_handler_captures_trace():
    with raises(MyErr) as excinfo:
        _raise_and_wrap()
    err = excinfo.value
    assert err.cause.__class__ is ValueError
    assert err.root_cause is err.cause
    assert err.full_trace
    assert err._tb
    assert err._stack
    assert err.full_trace == err._stack[:-1] + err._tb
    rendered = str(err)
    assert rendered.startswith('while handling --- ')
    assert 'Wrapped traceback (most recent call last):' in rendered
    assert '(caused by ValueError: root)' in rendered
    assert 'Traceback (most recent call last):' in err.get_str()


def test_format_exc():
    assert _format_exc(ValueError('boom')) == 'ValueError: boom'
    assert _format_exc(ValueError('boom'), 'custom') == 'ValueError: custom'


def test_deferred_line_reads_file():
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, 'w') as f:
            f.write('first line\nsecond line\n')
        line = _DeferredLine(path, 2, {'__name__': 'mod', 'other': 'x'})
        assert line.module_globals == {'__name__': 'mod'}
        assert str(line) == 'second line'
        assert repr(line) == "'second line'"
        assert len(line) == len('second line')
        assert line.strip() == 'second line'

        same = _DeferredLine(path, 2)
        other = _DeferredLine(path, 1)
        assert line == same
        assert line != other
        assert not (line != same)
        assert line != other

        missing = _DeferredLine(path, 999)
        assert str(missing) == ''
        assert repr(missing) == "''"
        assert len(missing) == 0
        assert missing.strip() == ''
    finally:
        os.remove(path)


def test_extract_from_frame_default():
    items = _extract_from_frame(limit=2)
    assert len(items) <= 2
    assert all(isinstance(item, _TBItem) for item in items)
    assert any(item.name == 'test_extract_from_frame_default' for item in items)
    assert any(item.filename == __file__ for item in items)
    assert str(items[0].frame_id) in repr(items[0])


def test_extract_from_frame_explicit_limit():
    items = _extract_from_frame(sys._getframe(), limit=1)
    assert len(items) == 1


def test_extract_from_tb():
    try:
        1 / 0
    except ZeroDivisionError:
        tb = sys.exc_info()[2]
    items = _extract_from_tb(tb)
    assert items
    assert items[-1].name == 'test_extract_from_tb'
    assert items[-1].filename == __file__
    assert len(_extract_from_tb(tb, limit=1)) == 1


def test_math_lol_wraps_zero_division():
    with raises(MathError) as excinfo:
        math_lol()
    err = excinfo.value
    assert isinstance(err, ValueError)
    assert err.cause.__class__ is ZeroDivisionError
    assert err.root_cause.__class__ is ZeroDivisionError
    assert 'ya done messed up' in str(err)
    assert 'Wrapped traceback' in str(err)


def test_main_wraps_math_error():
    with raises(MathError) as excinfo:
        excutils_main()
    err = excinfo.value
    assert err._get_message() == 'hi'
    assert err.cause.__class__ is MathError
    # root cause propagates all the way back to the ZeroDivisionError
    assert err.root_cause.__class__ is ZeroDivisionError
