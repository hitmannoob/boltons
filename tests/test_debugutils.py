import signal
import sys
import types

from pytest import raises

import boltons.debugutils as debugutils


def _recorder(events):
    names = ('event', 'label', 'obj', 'attr_name', 'args', 'kwargs')

    def hook(*a, **kw):
        record = dict(zip(names, a))
        record.update(kw)
        events.append(record)

    return hook


def test_pdb_on_signal_explicit(monkeypatch):
    calls = []
    fake_pdb = types.SimpleNamespace(set_trace=lambda: calls.append('trace'))
    monkeypatch.setitem(sys.modules, 'pdb', fake_pdb)

    sig = signal.SIGUSR1
    original = signal.getsignal(sig)
    try:
        assert debugutils.pdb_on_signal(sig) is None
        handler = signal.getsignal(sig)
        assert handler is not original

        handler(sig, None)
        assert calls == ['trace']
        # The handler restores the previous one before tracing, then
        # re-installs itself so a later signal can be traced again.
        assert signal.getsignal(sig) is not original
    finally:
        signal.signal(sig, original)


def test_pdb_on_signal_defaults_to_sigint(monkeypatch):
    fake_pdb = types.SimpleNamespace(set_trace=lambda: None)
    monkeypatch.setitem(sys.modules, 'pdb', fake_pdb)

    original = signal.getsignal(signal.SIGINT)
    try:
        debugutils.pdb_on_signal()
        assert signal.getsignal(signal.SIGINT) is not original
    finally:
        signal.signal(signal.SIGINT, original)


def test_pdb_on_exception(monkeypatch):
    post_mortem = []
    fake_pdb = types.SimpleNamespace(
        post_mortem=lambda tb: post_mortem.append(tb))
    monkeypatch.setitem(sys.modules, 'pdb', fake_pdb)

    printed = []
    monkeypatch.setattr(
        'traceback.print_tb',
        lambda tb, limit=None: printed.append((tb, limit)))

    original = sys.excepthook
    try:
        assert debugutils.pdb_on_exception(limit=7) is None
        hook = sys.excepthook
        assert hook is not original

        try:
            raise ValueError('kaboom')
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            hook(exc_type, exc_value, exc_tb)

        assert post_mortem == [exc_tb]
        assert printed == [(exc_tb, 7)]
    finally:
        sys.excepthook = original


def test_trace_print_hook_get(capsys):
    obj = object()
    debugutils.trace_print_hook('get', 'label', obj, 'attr', result=5)
    out = capsys.readouterr().out
    assert 'get' in out
    assert 'label' in out
    assert 'attr -> 5' in out


def test_trace_print_hook_set(capsys):
    obj = object()
    debugutils.trace_print_hook('set', 'lab', obj, 'attr', args=('value',))
    out = capsys.readouterr().out
    assert 'attr =' in out
    assert "'value'" in out


def test_trace_print_hook_del(capsys):
    obj = object()
    debugutils.trace_print_hook('del', 'lab', obj, 'gone')
    out = capsys.readouterr().out
    assert 'gone' in out
    assert '=' not in out


def test_trace_print_hook_call_kwargs_and_result(capsys):
    obj = object()
    debugutils.trace_print_hook('call', 'lab', obj, 'meth',
                                args=(1, 2), kwargs={'x': 3}, result=9)
    out = capsys.readouterr().out
    assert 'meth(1, 2, x=3)' in out
    assert '-> 9' in out


def test_wrap_trace_which_sequence():
    events = []

    class Target:
        def __init__(self):
            self.value = 0

    target = Target()
    wrapped = debugutils.wrap_trace(
        target, hook=_recorder(events), which=['__setattr__'])
    wrapped.value = 1
    assert target.value == 1
    assert any(e['event'] == 'set' and e['attr_name'] == 'value'
               for e in events)


def test_wrap_trace_which_callable():
    events = []

    class Target:
        def method(self):
            return 'ok'

    wrapped = debugutils.wrap_trace(
        Target(), hook=_recorder(events),
        which=lambda name, val: name == 'method')
    assert wrapped.method() == 'ok'
    assert any(e['event'] == 'call' and e['attr_name'] == 'method'
               for e in events)


def test_wrap_trace_bad_which():
    with raises(TypeError):
        debugutils.wrap_trace(object(), which=123)


def test_wrap_trace_delattr_event():
    events = []

    class Target:
        pass

    target = Target()
    target.temp = 1
    wrapped = debugutils.wrap_trace(
        target, hook=_recorder(events), events='del')
    del wrapped.temp
    assert not hasattr(target, 'temp')
    assert any(e['event'] == 'del' and e['attr_name'] == 'temp'
               for e in events)


def test_wrap_trace_raise_not_suppressed():
    class Target:
        def boom(self):
            raise ValueError('boom')

    wrapped = debugutils.wrap_trace(
        Target(), hook=lambda *a, **kw: False, events='raise')
    with raises(ValueError):
        wrapped.boom()


def test_wrap_trace_without_raise_event():
    class Target:
        def boom(self):
            raise ValueError('boom')

    events = []
    wrapped = debugutils.wrap_trace(
        Target(), hook=_recorder(events), events='call')
    with raises(ValueError):
        wrapped.boom()
    assert [e['event'] for e in events] == ['call']


def test_wrap_trace_skips_unreadable_attributes():
    class Target:
        def ok(self):
            return 'fine'

        @property
        def broken(self):
            raise RuntimeError('cannot read me')

    wrapped = debugutils.wrap_trace(Target(), hook=lambda *a, **kw: None)
    assert wrapped.ok() == 'fine'
    assert isinstance(wrapped, Target)


def test_wrap_trace_uses_label():
    events = []

    class Target:
        def method(self):
            return 1

    wrapped = debugutils.wrap_trace(
        Target(), hook=_recorder(events),
        label='mylabel', which='method', events='call')
    wrapped.method()
    assert events[0]['label'] == 'mylabel'
    assert events[0]['obj'] is not None


def test_wrap_trace_raise_suppressed_returns_none():
    class Target:
        def boom(self):
            raise ValueError('boom')

    wrapped = debugutils.wrap_trace(
        Target(), hook=lambda *a, **kw: True, which='boom')
    assert wrapped.boom() is None


def test_wrap_trace_lowercase_class_name():
    class lowercase:
        def ping(self):
            return 'pong'

    wrapped = debugutils.wrap_trace(lowercase(), which='ping')
    assert type(wrapped).__name__ == 'traced_lowercase'
    assert wrapped.ping() == 'pong'


def test_wrap_trace_class_object_is_not_wrappable():
    class Target:
        def method(self):
            return 1

    with raises(TypeError):
        debugutils.wrap_trace(Target, which='method')
