from collections import namedtuple

from pytest import raises

from boltons.debugutils import wrap_trace


def test_trace_dict():
    target = {}
    wrapped = wrap_trace(target)

    assert target is not wrapped
    assert isinstance(wrapped, dict)

    wrapped['a'] = 'A'
    assert target['a'] == 'A'
    assert len(wrapped) == len(target)

    wrapped.pop('a')
    assert 'a' not in target

    with raises(AttributeError):
        wrapped.nonexistent_attr = 'nope'

    return


def test_trace_bytes():
    target = b'Hello'

    wrapped = wrap_trace(target)

    assert target is not wrapped
    assert isinstance(wrapped, bytes)

    assert len(wrapped) == len(target)
    assert wrapped.decode('utf-8') == 'Hello'
    assert wrapped.lower() == target.lower()


def test_trace_exc():
    class TestException(Exception):
        pass

    target = TestException('exceptions can be a good thing')
    wrapped = wrap_trace(target)

    try:
        raise wrapped
    except TestException as te:
        assert te.args == target.args


def test_trace_raise_suppressed():
    class Target:
        def boom(self):
            raise ValueError('boom')

    wrapped = wrap_trace(Target(), hook=lambda **kw: True, events='raise')
    assert wrapped.boom() is None


def test_trace_which():
    class Config:
        def __init__(self, value):
            self.value = value

    config = Config('first')
    wrapped = wrap_trace(config, which='__setattr__')

    wrapped.value = 'second'
    assert config.value == 'second'


def test_trace_namedtuple():
    TargetType = namedtuple('TargetType', 'x y z')
    target = TargetType(1, 2, 3)

    wrapped = wrap_trace(target)

    assert wrapped == (1, 2, 3)


def test_trace_oldstyle():
    class Oldie:
        test = object()

        def get_test(self):
            return self.test

    oldie = Oldie()

    wrapped = wrap_trace(oldie)
    assert wrapped.get_test() is oldie.test

    return


def test_pdb_on_signal_installs_and_restores_handler():
    import signal
    from boltons.debugutils import pdb_on_signal

    signum = signal.SIGUSR1
    old = signal.getsignal(signum)
    try:
        assert pdb_on_signal(signum) is None
        installed = signal.getsignal(signum)
        assert callable(installed)
        assert installed is not old
    finally:
        signal.signal(signum, old)


def test_pdb_on_exception_installs_hook(monkeypatch):
    import pdb
    import sys
    from boltons.debugutils import pdb_on_exception

    seen = []
    monkeypatch.setattr(pdb, 'post_mortem', lambda tb: seen.append(tb))
    old = sys.excepthook
    try:
        assert pdb_on_exception(limit=5) is None
        hook = sys.excepthook
        assert hook is not old
        try:
            raise ValueError('boom')
        except ValueError:
            tb = sys.exc_info()[2]
        hook(ValueError, ValueError('boom'), tb)
        assert seen == [tb]
    finally:
        sys.excepthook = old


def test_trace_print_hook_formats_events(capsys):
    from boltons.debugutils import trace_print_hook

    class Thing:
        pass

    obj = Thing()
    trace_print_hook('get', 'L', obj, 'attr_name', result=1)
    trace_print_hook('set', 'L', obj, 'attr_name', args=(2,))
    trace_print_hook('del', 'L', obj, 'attr_name')
    trace_print_hook('call', 'L', obj, 'method', args=(1,), kwargs={'x': 2})
    trace_print_hook('return', 'L', obj, 'method', result=3)

    out = capsys.readouterr().out
    assert 'Thing.attr_name -> 1' in out
    assert 'Thing.attr_name = 2' in out
    assert 'Thing.attr_name\n' in out
    assert 'method(1, x=2)' in out
    assert 'method() -> 3' in out


def test_trace_which_container_and_invalid():
    from boltons.debugutils import wrap_trace

    class Config:
        def __init__(self):
            self.value = 1
            self.other = 2

        def get_value(self):
            return self.value

    calls = []
    wrapped = wrap_trace(Config(), which=['get_value'],
                         hook=lambda **kw: calls.append(kw['attr_name']))
    assert wrapped.get_value() == 1
    assert calls == ['get_value', 'get_value']

    with raises(TypeError):
        wrap_trace(Config(), which=42)


def test_trace_raise_reraised_when_hook_falsy():
    class Target:
        def boom(self):
            raise ValueError('boom')

    wrapped = wrap_trace(Target(), hook=lambda **kw: False, events='raise')
    with raises(ValueError):
        wrapped.boom()


def test_trace_delattr_and_no_raise_events():
    from boltons.debugutils import wrap_trace

    class Config:
        def __init__(self):
            self.value = 1

        def get_value(self):
            return self.value

        def __delattr__(self, name):
            object.__delattr__(self, name)

    deleted = []
    wrapped = wrap_trace(Config(), events='del',
                         hook=lambda *a: deleted.append(a[3]))
    del wrapped.value
    assert deleted == ['value']

    wrapped = wrap_trace(Config(), events='call',
                         hook=lambda **kw: None)
    assert wrapped.get_value() == 1


def test_trace_skips_unreadable_attributes():
    from boltons.debugutils import wrap_trace

    class Broken:
        @property
        def broken(self):
            raise RuntimeError('no reading this')

        def ok(self):
            return 'ok'

    wrapped = wrap_trace(Broken(), which='ok')
    assert wrapped.ok() == 'ok'
