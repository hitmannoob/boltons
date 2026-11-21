import builtins
import warnings

import pytest

from boltons.easterutils import gobs_program


def test_gobs_program_prints_penus_forever(monkeypatch):
    calls = []

    def fake_print(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 3:
            raise RuntimeError('stop gobs')

    monkeypatch.setattr(builtins, 'print', fake_print)

    with pytest.raises(RuntimeError, match='stop gobs'):
        gobs_program()

    assert calls == [(('Penus',), {'end': ' '})] * 3


def test_gobs_program_runs_as_main(monkeypatch):
    import runpy

    calls = []

    def fake_print(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError('stop gobs')

    monkeypatch.setattr(builtins, 'print', fake_print)

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        with pytest.raises(RuntimeError, match='stop gobs'):
            runpy.run_module('boltons.easterutils', run_name='__main__')

    assert calls == [(('Penus',), {'end': ' '})]
