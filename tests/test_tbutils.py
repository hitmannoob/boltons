import json
import sys
from io import StringIO

from boltons.tbutils import (TracebackInfo,
                             ExceptionInfo,
                             print_exception,
                             fix_print_exception,
                             ContextualCallpoint,
                             ContextualExceptionInfo)



def test_exception_info():
    # test ExceptionInfo and TracebackInfo and hooks, via StringIOs
    builtin_exc_hook = sys.excepthook
    fix_print_exception()
    tbi_str = ''

    def test():
        raise ValueError('yay fun')

    fake_stderr1 = StringIO()
    fake_stderr2 = StringIO()
    sys.stderr = fake_stderr1

    try:
        test()
    except:
        exc, _, exc_traceback = sys.exc_info()
        tbi = TracebackInfo.from_traceback(exc_traceback)
        exc_info = ExceptionInfo.from_exc_info(*sys.exc_info())
        exc_info2 = ExceptionInfo.from_current()
        tbi_str = str(tbi)
        print_exception(*sys.exc_info(), file=fake_stderr2)
        new_exc_hook_res = fake_stderr2.getvalue()
        builtin_exc_hook(*sys.exc_info())
        builtin_exc_hook_res = fake_stderr1.getvalue()
    finally:
        sys.stderr = sys.__stderr__

    # Single frame
    single_frame_str = tbi.frames[-1].tb_frame_str()
    assert 'in test' in single_frame_str
    assert 'yay fun' in single_frame_str

    # Traceback info
    assert len(tbi_str.splitlines()) == 5
    assert 'yay fun' in tbi_str

    # Full except hook output
    assert 'ValueError: yay fun' in new_exc_hook_res
    assert "ValueError('yay fun')" in new_exc_hook_res
    assert len(new_exc_hook_res) > len(tbi_str)

    if sys.version_info <= (3, 12):
        # output diverges with Python 3.13+, see https://github.com/mahmoud/boltons/issues/365
        # TLDR tbutils only has minimal handling for anchors (e.g., ~~~~^^)
        assert new_exc_hook_res == builtin_exc_hook_res


def test_contextual():
    def func1():
        return func2()
    def func2():
        x = 5
        return func3()
    def func3():
        return ContextualCallpoint.from_current(level=2)

    callpoint = func1()
    assert callpoint.func_name == 'func2'
    line = str(callpoint.line)
    assert line.startswith(' ')
    assert line.strip() == 'return func3()'
    assert 'func2' in repr(callpoint)

    try:
        json.dumps(callpoint.to_dict())
    except TypeError:
        raise AssertionError("to_dict result is not JSON serializable")

    def func_a():
        a = 1
        raise Exception('func_a exception')
    def func_b():
        b = 2
        return func_a()
    def func_c():
        c = 3
        return func_b()

    try:
        func_c()
    except Exception as e:
        ctx_ei = ContextualExceptionInfo.from_current()
        ctx_ei_str = ctx_ei.get_formatted()

    ctx_ei_lines = ctx_ei_str.splitlines()
    assert ctx_ei_lines[-1] == 'Exception: func_a exception'
    assert ctx_ei_lines[0] == 'Traceback (most recent call last):'
    assert len(ctx_ei_lines) == 10
    assert "Exception('func_a exception')" in ctx_ei_str
    assert ctx_ei.tb_info.frames[2].local_reprs['b'] == '2'


def test_callpoint_to_dict_skips_missing_slots():
    from boltons.tbutils import Callpoint

    cp = Callpoint('mod', '/tmp/mod.py', 'func', 12, 3, line='x = 1')
    del cp.line
    d = cp.to_dict()
    assert 'line' not in d
    assert d['func_name'] == 'func'
    assert d['lineno'] == 12


def test_callpoint_empty_repr_uses_default():
    from boltons.tbutils import Callpoint

    cp = Callpoint('', '', '', 0, 0, line=None)
    assert repr(cp).startswith('<boltons.tbutils.Callpoint object at')


def test_deferred_line_equality():
    from boltons.tbutils import _DeferredLine

    a = _DeferredLine('/tmp/a.py', 1)
    b = _DeferredLine('/tmp/a.py', 1)
    c = _DeferredLine('/tmp/a.py', 2)
    assert a == b
    assert not (a != b)
    assert a != c
    assert not (a == c)


def test_deferred_line_missing_line_is_empty(monkeypatch):
    import linecache
    from boltons.tbutils import _DeferredLine

    def raise_keyerror(*a, **kw):
        raise KeyError('gone')

    monkeypatch.setattr(linecache, 'getline', raise_keyerror)
    dl = _DeferredLine('/tmp/does-not-matter.py', 7)
    assert str(dl) == ''
    assert repr(dl) == "''"
    assert len(dl) == 0


def test_traceback_info_from_frame_limit():
    tbi = TracebackInfo.from_frame(limit=2)
    assert len(tbi) == 2
    assert tbi.frames[-1].func_name == 'test_traceback_info_from_frame_limit'
    assert list(tbi)[-1] is tbi.frames[-1]

    one = TracebackInfo.from_frame(limit=1)
    assert len(one) == 1

    default_limit = TracebackInfo.from_frame()
    assert len(default_limit) >= 1


def test_traceback_info_from_traceback_requires_exception():
    try:
        TracebackInfo.from_traceback()
    except ValueError as e:
        assert 'no tb set' in str(e)
    else:
        raise AssertionError('expected ValueError')


def test_traceback_info_roundtrip_and_repr():
    tbi = TracebackInfo.from_frame(limit=1)
    d = tbi.to_dict()
    assert isinstance(d['frames'], list)
    assert d['frames'][0]['func_name'] == 'test_traceback_info_roundtrip_and_repr'

    rebuilt = TracebackInfo.from_dict(d)
    assert len(rebuilt) == len(tbi)
    assert rebuilt.frames[0]['lineno'] == tbi.frames[0].lineno

    assert repr(tbi).startswith('<TracebackInfo frames=1 last=')
    assert repr(TracebackInfo([])) == '<TracebackInfo frames=0>'


def test_exception_info_module_prefix_and_dict():
    class CustomError(Exception):
        pass

    CustomError.__module__ = 'fake.custom.mod'
    try:
        raise CustomError('boom')
    except CustomError:
        ei = ExceptionInfo.from_current()

    assert ei.exc_type == 'fake.custom.mod.CustomError'
    assert ei.exc_msg == 'boom'
    assert ei.get_formatted_exception_only() == 'fake.custom.mod.CustomError: boom'
    assert ei.get_formatted().endswith('fake.custom.mod.CustomError: boom')

    d = ei.to_dict()
    assert d['exc_type'] == 'fake.custom.mod.CustomError'
    assert d['exc_msg'] == 'boom'
    assert d['exc_tb'] == ei.tb_info.to_dict()
    assert repr(ei).startswith('<ExceptionInfo [fake.custom.mod.CustomError: boom] (')


def test_exception_info_repr_without_frames():
    ei = ExceptionInfo('ValueError', 'nope', object())
    assert repr(ei) == '<ExceptionInfo [ValueError: nope] (0 frames)>'


def test_contextual_local_repr_survives_unprintable():
    class BadRepr:
        def __repr__(self):
            raise RuntimeError('cannot repr')

    def raises():
        bad = BadRepr()
        raise RuntimeError('inner')

    try:
        raises()
    except RuntimeError:
        cei = ContextualExceptionInfo.from_current()

    frame = cei.tb_info.frames[-1]
    assert frame.local_reprs['bad'] == '<unprintable BadRepr object>'


def test_contextual_callpoint_to_dict_trims_blank_pre_lines(tmp_path):
    path = tmp_path / 'ctx.py'
    path.write_text('\nx = 1\ntrigger\n')
    from boltons.tbutils import _DeferredLine

    cp = ContextualCallpoint(str(path), str(path), 'func', 3, 0, line=None)
    cp.pre_lines = [_DeferredLine(str(path), 1), _DeferredLine(str(path), 2)]
    d = cp.to_dict()
    assert d['pre_lines'] == [{'lineno': 2, 'line': 'x = 1'}]


def test_format_exception_only_none_type():
    from boltons.tbutils import format_exception_only

    assert format_exception_only(None, None) == ['None\n']


def test_format_exception_only_module_prefix_and_empty_value():
    from boltons.tbutils import format_exception_only

    class CustomError(Exception):
        pass

    CustomError.__module__ = 'fake.mod'
    assert format_exception_only(CustomError, CustomError('hi')) == ['fake.mod.CustomError: hi\n']
    assert format_exception_only(ValueError, ValueError('')) == ['ValueError\n']


def test_format_exception_only_syntax_error():
    from boltons.tbutils import format_exception_only

    try:
        compile('value =', 'broken.py', 'exec')
    except SyntaxError as se:
        lines = format_exception_only(SyntaxError, se)

    text = ''.join(lines)
    assert 'File "broken.py", line 1' in text
    assert 'value =' in text
    assert '^' in text
    assert text.endswith('SyntaxError: invalid syntax\n')


def test_format_exception_only_unprintable_value():
    from boltons.tbutils import format_exception_only

    class BadStr:
        def __str__(self):
            raise RuntimeError('no')

    out = format_exception_only(ValueError, BadStr())
    assert out == ['ValueError: <unprintable BadStr object>\n']


def test_print_exception_defaults_to_stderr():
    fake = StringIO()
    old_stderr = sys.stderr
    sys.stderr = fake
    try:
        print_exception(ValueError, ValueError('to stderr'), None)
    finally:
        sys.stderr = old_stderr
    assert fake.getvalue() == 'ValueError: to stderr\n'
