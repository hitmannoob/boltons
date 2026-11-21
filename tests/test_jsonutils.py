import os
import sys

from boltons.jsonutils import (JSONLIterator,
                               DEFAULT_BLOCKSIZE,
                               reverse_iter_lines)

CUR_PATH = os.path.dirname(os.path.abspath(__file__))
NEWLINES_DATA_PATH = CUR_PATH + '/newlines_test_data.txt'
JSONL_DATA_PATH = CUR_PATH + '/jsonl_test_data.txt'


def _test_reverse_iter_lines(filename, blocksize=DEFAULT_BLOCKSIZE):
    fo = open(filename)
    reference = fo.read()
    fo.seek(0, os.SEEK_SET)
    rev_lines = list(reverse_iter_lines(fo, blocksize))
    assert '\n'.join(rev_lines[::-1]) == reference


def _test_reverse_iter_lines_bytes(filename, blocksize=DEFAULT_BLOCKSIZE):
    fo = open(filename, 'rb')
    reference = fo.read()
    fo.seek(0, os.SEEK_SET)
    rev_lines = list(reverse_iter_lines(fo, blocksize))
    assert os.linesep.encode('ascii').join(rev_lines[::-1]) == reference



def test_reverse_iter_lines():
    for blocksize in (2, 4, 16, 4096):
        _test_reverse_iter_lines(NEWLINES_DATA_PATH, blocksize)
        _test_reverse_iter_lines_bytes(NEWLINES_DATA_PATH, blocksize)


def test_jsonl_iterator():
    ref = [{'4': 4}, {'3': 3}, {'2': 2}, {'1': 1}, {}]
    jsonl_iter = JSONLIterator(open(JSONL_DATA_PATH), reverse=True)
    jsonl_list = list(jsonl_iter)
    assert jsonl_list == ref


class _CappedReadFile:
    """Wraps a file object, raising if read() is called more than
    max_reads times, so a non-terminating read loop fails fast
    instead of hanging the test suite."""
    def __init__(self, fo, max_reads=100):
        self._fo = fo
        self._reads = 0
        self._max_reads = max_reads

    def read(self, size=-1):
        self._reads += 1
        if self._reads > self._max_reads:
            raise RuntimeError('read() called more than %s times,'
                               ' likely an infinite loop' % self._max_reads)
        return self._fo.read(size)

    def __iter__(self):
        return iter(self._fo)

    def __getattr__(self, name):
        return getattr(self._fo, name)


def test_jsonl_iterator_mid_last_line_seek_terminates(tmp_path):
    # a rel_seek landing mid-final-line of a file with no trailing
    # newline used to loop forever in _align_to_newline
    path = tmp_path / 'no_trailing_newline.jsonl'
    path.write_text('{"1": 1}\n{"2": 2}')
    fo = _CappedReadFile(open(str(path)))
    jsonl_iter = JSONLIterator(fo, rel_seek=0.9)
    assert list(jsonl_iter) == []


def test_jsonl_iterator_rel_seek_negative():
    # negative rel_seek used to normalize to >1.0, seeking past EOF
    # and looping forever in _align_to_newline
    ref = list(JSONLIterator(open(JSONL_DATA_PATH)))
    fo = _CappedReadFile(open(JSONL_DATA_PATH))
    tail = list(JSONLIterator(fo, rel_seek=-0.5))
    assert tail
    assert tail == list(JSONLIterator(open(JSONL_DATA_PATH), rel_seek=0.5))
    assert tail == ref[len(ref) - len(tail):]


def test_jsonl_explicit_end_seek(tmp_path):
    path = tmp_path / 'records.jsonl'
    path.write_text('{"n": 1}\n{"n": 2}\n')
    with path.open('rb', buffering=0) as stream:
        assert list(JSONLIterator(stream, reverse=True, rel_seek=1.0)) == [{'n': 2}, {'n': 1}]
    with path.open() as stream:
        assert list(JSONLIterator(stream, rel_seek=1.0)) == []


def test_jsonl_relative_seek_binary_matches_text(tmp_path):
    path = tmp_path / 'records.jsonl'
    path.write_bytes(b'{"n": 1}\n{"n": 2}\n{"n": 3}\n')
    with path.open('rb') as binary, path.open() as text:
        assert list(JSONLIterator(binary, rel_seek=0.4)) == list(JSONLIterator(text, rel_seek=0.4))


def test_reverse_iter_lines_uses_file_encoding(tmp_path):
    path = tmp_path / 'latin1.txt'
    path.write_bytes('café\nfin'.encode('latin-1'))
    with path.open(encoding='latin-1') as stream:
        assert list(reverse_iter_lines(stream)) == ['fin', 'café']


def test_reverse_iter_lines_uses_explicit_binary_encoding():
    from io import BytesIO

    stream = BytesIO('café\nfin'.encode('latin-1'))
    assert list(reverse_iter_lines(stream, encoding='latin-1')) == ['fin', 'café']


def test_reverse_iter_lines_keeps_text_stream_attached(tmp_path):
    path = tmp_path / 'lines.txt'
    path.write_text('first\nsecond')
    with path.open() as stream:
        assert list(reverse_iter_lines(stream)) == ['second', 'first']
        stream.seek(0)
        assert stream.read() == 'first\nsecond'


def test_reverse_iter_lines_leading_empty_lines():
    from io import BytesIO
    data = b'\n\nfirst\nsecond\n'
    for blocksize in (2, 4, 4096):
        rev = list(reverse_iter_lines(BytesIO(data), blocksize=blocksize))
        assert rev == [b'', b'second', b'first', b'', b'']
        assert b'\n'.join(reversed(rev)) == data
    assert list(reverse_iter_lines(BytesIO(b'\n'))) == [b'', b'']


def test_reverse_iter_lines_stringio():
    from io import StringIO
    assert list(reverse_iter_lines(StringIO('a\nb\n'))) == ['', 'b', 'a']
    assert list(reverse_iter_lines(StringIO('x\ny'), blocksize=2)) == ['y', 'x']


def test_jsonl_iterator_text_cur_byte_pos(tmp_path):
    path = tmp_path / 'records.jsonl'
    path.write_bytes(b'{"1": 1}\n{"2": 2}\n')  # no CRLF translation on Windows
    with path.open() as stream:
        jsonl_iter = JSONLIterator(stream)
        assert next(jsonl_iter) == {'1': 1}
        assert jsonl_iter.cur_byte_pos == len('{"1": 1}\n')
        assert list(jsonl_iter) == [{'2': 2}]


def test_jsonl_iterator_rejects_out_of_range_rel_seek(tmp_path):
    import pytest

    path = tmp_path / 'records.jsonl'
    path.write_text('{"n": 1}\n')
    with path.open('rb') as stream:
        for bad in (1.5, -1.0, 2):
            with pytest.raises(ValueError) as excinfo:
                JSONLIterator(stream, rel_seek=bad)
            assert 'rel_seek' in str(excinfo.value)


def test_jsonl_iterator_rel_seek_zero_reads_from_start(tmp_path):
    path = tmp_path / 'records.jsonl'
    path.write_text('{"n": 1}\n{"n": 2}\n{"n": 3}\n')
    with path.open('rb') as stream:
        assert list(JSONLIterator(stream, rel_seek=0.0)) == [
            {'n': 1}, {'n': 2}, {'n': 3}]


def test_jsonl_iterator_raises_on_corrupt_line_by_default(tmp_path):
    import pytest

    path = tmp_path / 'records.jsonl'
    path.write_text('{"n": 1}\nnot json\n{"n": 3}\n')
    with path.open('rb') as stream:
        jsonl_iter = JSONLIterator(stream)
        assert next(jsonl_iter) == {'n': 1}
        with pytest.raises(ValueError):
            next(jsonl_iter)


def test_jsonl_iterator_ignore_errors_skips_corrupt_lines(tmp_path):
    path = tmp_path / 'records.jsonl'
    path.write_text('{"n": 1}\nnot json\n\n{"n": 3}\n')
    with path.open('rb') as stream:
        jsonl_iter = JSONLIterator(stream, ignore_errors=True)
        assert list(jsonl_iter) == [{'n': 1}, {'n': 3}]


def test_jsonl_iterator_skips_blank_and_whitespace_lines(tmp_path):
    path = tmp_path / 'records.jsonl'
    path.write_text('\n   \n{"n": 1}\n\t\n{"n": 2}\n')
    with path.open('rb') as stream:
        assert list(JSONLIterator(stream)) == [{'n': 1}, {'n': 2}]


def test_jsonl_script_help_exits_after_usage(monkeypatch, capsys):
    import runpy

    monkeypatch.setattr(sys, 'argv', ['jsonutils', '--help'])
    from boltons import jsonutils as _jsonutils
    runpy.run_path(_jsonutils.__file__, run_name='__main__')
    out = capsys.readouterr().out
    assert 'loads one or more JSON Line files' in out


def test_jsonl_script_verbose_counts_objects(tmp_path, monkeypatch, capsys):
    import runpy

    path = tmp_path / 'records.jsonl'
    path.write_text(''.join('{"n": %d}\n' % i for i in range(100)))
    monkeypatch.setattr(sys, 'argv', ['jsonutils', '-v', str(path)])
    from boltons import jsonutils as _jsonutils
    runpy.run_path(_jsonutils.__file__, run_name='__main__')
    out = capsys.readouterr().out
    assert 'files checked: 1' in out
    assert 'objects loaded: 100' in out
    assert '.' in out
    assert '100\n' in out


def test_jsonl_script_reports_corrupt_line(tmp_path, monkeypatch, capsys):
    import runpy

    path = tmp_path / 'records.jsonl'
    path.write_text('not json\n')
    monkeypatch.setattr(sys, 'argv', ['jsonutils', str(path)])
    from boltons import jsonutils as _jsonutils
    runpy.run_path(_jsonutils.__file__, run_name='__main__')
    out = capsys.readouterr().out
    assert 'error reading object #1 around byte' in out
    assert str(path) in out
