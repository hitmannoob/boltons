import getpass
import json
import os
import platform
import socket
import sys

import pytest

from boltons import ecoutils


def test_basic():
    # basic sanity test
    prof = ecoutils.get_profile()

    assert prof['python']['bin'] == sys.executable


def test_scrub():
    prof = ecoutils.get_profile(scrub=True)

    assert prof['username'] == '-'
    assert prof['hostname'] == '-'
    assert prof['hostfqdn'] == '-'
    assert prof['cwd'] == '-'
    assert prof['uname']['node'] == '-'
    assert prof['python']['bin'] == '-'
    assert prof['python']['argv'] == '-'


def test_scrub_does_not_resolve_the_host(monkeypatch):
    def unreachable(*args):
        raise AssertionError('scrubbed profile resolved the host name')

    monkeypatch.setattr(socket, 'gethostname', unreachable)
    monkeypatch.setattr(socket, 'getfqdn', unreachable)

    prof = ecoutils.get_profile(scrub=True)

    assert prof['hostname'] == '-'
    assert prof['hostfqdn'] == '-'


def test_scrub_does_not_read_the_cwd(monkeypatch):
    calls = []
    real_getcwd = os.getcwd

    def recording_getcwd():
        calls.append('getcwd')
        return real_getcwd()

    monkeypatch.setattr(os, 'getcwd', recording_getcwd)

    prof = ecoutils.get_profile(scrub=True)

    assert calls == []

    assert prof['cwd'] == '-'


def test_get_profile_keys_and_json_serializable():
    prof = ecoutils.get_profile()

    assert prof['_eco_version'] == ecoutils.ECO_VERSION
    assert prof['guid'] == str(ecoutils.INSTANCE_ID)
    assert isinstance(prof['python'], dict)
    assert isinstance(prof['python']['version_info'], list)
    assert prof['python']['features']['unicode_wide'] in (True, False)
    # the documented contract is that profiles can be shipped as JSON
    assert json.loads(json.dumps(prof))['guid'] == prof['guid']


def test_get_profile_rejects_unknown_keywords():
    with pytest.raises(TypeError) as excinfo:
        ecoutils.get_profile(unexpected=1, other=2)

    message = str(excinfo.value)
    assert 'unexpected' in message
    assert 'other' in message


def test_get_profile_username_falls_back_on_error(monkeypatch):
    def broken_getuser():
        raise OSError('no passwd entry')

    monkeypatch.setattr(getpass, 'getuser', broken_getuser)

    prof = ecoutils.get_profile()

    assert prof['username'] == ''


def test_get_profile_linux_dist_falls_back_on_error(monkeypatch):
    def broken_linux_distribution():
        raise RuntimeError('platform does not expose it')

    monkeypatch.setattr(platform, 'linux_distribution',
                        broken_linux_distribution, raising=False)

    prof = ecoutils.get_profile(scrub=True)

    assert prof['linux_dist_name'] == ''
    assert prof['linux_dist_version'] == ''


def test_get_profile_umask_is_three_octal_digits():
    prof = ecoutils.get_profile(scrub=True)

    assert prof['umask'].startswith('0')
    assert len(prof['umask']) >= 3
    int(prof['umask'], 8)  # must parse as octal


def test_dumps_sorts_and_honours_indent():
    value = {'b': 1, 'a': [2, 3]}

    compact = ecoutils.dumps(value, 0)
    pretty = ecoutils.dumps(value, 2)

    assert compact == json.dumps(value, sort_keys=True)
    assert pretty == json.dumps(value, sort_keys=True, indent=2)
    assert '\n' not in compact
    assert '\n' in pretty


def test_get_profile_json_returns_json_text():
    compact = ecoutils.get_profile_json()
    pretty = ecoutils.get_profile_json(indent=True)

    assert json.loads(compact)['python']['bin'] == sys.executable
    assert json.loads(pretty)['_eco_version'] == ecoutils.ECO_VERSION
    assert '\n' not in compact
    assert '\n' in pretty


def test_main_prints_pretty_json(capsys):
    ecoutils.main()

    out = capsys.readouterr().out
    parsed = json.loads(out)

    assert parsed['_eco_version'] == ecoutils.ECO_VERSION
    assert '\n' in out.strip()


def test_escape_shell_args_sh():
    assert ecoutils._escape_shell_args(['ls', '-l'], style='sh') == 'ls -l'
    assert ecoutils._escape_shell_args(['', 'x'], style='sh') == "'' x"
    assert ecoutils._escape_shell_args(['a b'], style='sh') == "'a b'"
    assert (ecoutils._escape_shell_args(["it's"], style='sh')
            == "'it'\"'\"'s'")


def test_escape_shell_args_rejects_unknown_style():
    with pytest.raises(ValueError) as excinfo:
        ecoutils._escape_shell_args(['x'], style='ps')

    message = str(excinfo.value)
    assert "'cmd'" in message
    assert "'sh'" in message


def test_escape_shell_args_default_style_follows_platform():
    args = ['a b', 'c']
    default_style = 'cmd' if sys.platform == 'win32' else 'sh'

    assert (ecoutils._escape_shell_args(args)
            == ecoutils._escape_shell_args(args, style=default_style))


def test_args2cmd_handles_spaces_tabs_and_empty():
    assert ecoutils._args2cmd([]) == ''
    assert ecoutils._args2cmd(['a', 'b']) == 'a b'
    assert ecoutils._args2cmd(['a b']) == '"a b"'
    assert ecoutils._args2cmd(['']) == '""'
    assert ecoutils._args2cmd(['a\tb']) == '"a\tb"'


def test_args2cmd_handles_backslashes_and_quotes():
    # backslashes not followed by a quote are passed through
    assert ecoutils._args2cmd(['a\\b']) == 'a\\b'
    # a quote gets a single backslash, existing backslashes would double
    assert ecoutils._args2cmd(['a"b']) == 'a' + '\\' + '"' + 'b'
    # trailing backslashes inside a quoted arg are doubled
    assert ecoutils._args2cmd(['a b\\']) == '"a b' + '\\\\' + '"'


def test_escape_shell_args_cmd_style():
    assert ecoutils._escape_shell_args(['a b', 'c'], style='cmd') == '"a b" c'


def test_escape_shell_args_defaults_to_cmd_on_win32(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')

    assert ecoutils._escape_shell_args(['a b']) == '"a b"'
