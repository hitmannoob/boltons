from boltons.tbutils import ParsedException


def test_parsed_exc_basic():
    _tb_str = """\
Traceback (most recent call last):
  File "example.py", line 2, in <module>
    plarp
NameError: name 'plarp' is not defined"""

    parsed_tb = ParsedException.from_string(_tb_str)
    print(parsed_tb)
    assert parsed_tb.exc_type == 'NameError'
    assert parsed_tb.exc_msg == "name 'plarp' is not defined"
    assert parsed_tb.frames == [{'source_line': 'plarp',
                                 'filepath': 'example.py',
                                 'lineno': '2',
                                 'funcname': '<module>'}]

    assert parsed_tb.to_string() == _tb_str


def test_parsed_exc_nosrcline():
    """just making sure that everything can be parsed even if there is
    a line without source and also if the exception has no message"""

    _tb_str = """\
Traceback (most recent call last):
  File "/home/mahmoud/virtualenvs/chert/bin/chert", line 9, in <module>
    load_entry_point('chert==0.2.1.dev0', 'console_scripts', 'chert')()
  File "/home/mahmoud/projects/chert/chert/core.py", line 1281, in main
    ch.process()
  File "/home/mahmoud/projects/chert/chert/core.py", line 741, in process
    self.load()
  File "<boltons.FunctionBuilder-0>", line 2, in load
  File "/home/mahmoud/projects/lithoxyl/lithoxyl/logger.py", line 291, in logged_func
    return func_to_log(*a, **kw)
  File "/home/mahmoud/projects/chert/chert/core.py", line 775, in load
    raise RuntimeError
RuntimeError"""

    parsed_tb = ParsedException.from_string(_tb_str)

    assert parsed_tb.exc_type == 'RuntimeError'
    assert parsed_tb.exc_msg == ''

    assert len(parsed_tb.frames) == 6
    assert parsed_tb.frames[3] == {'source_line': '',
                                   'filepath': '<boltons.FunctionBuilder-0>',
                                   'lineno': '2',
                                   'funcname': 'load'}
    assert parsed_tb.to_string() == _tb_str

_ANCHOR_TB_STR = """\
Traceback (most recent call last):
  File "main.py", line 3, in <module>
    print(add(1, "two"))
          ^^^^^^^^^^^^^
  File "add.py", line 2, in add
    return a + b
           ~~^~~
TypeError: unsupported operand type(s) for +: 'int' and 'str'"""


def test_parsed_exc_with_anchor():
    """parse a traceback with anchor lines beneath source lines"""
    parsed_tb = ParsedException.from_string(_ANCHOR_TB_STR)

    assert parsed_tb.exc_type == 'TypeError'
    assert parsed_tb.exc_msg == "unsupported operand type(s) for +: 'int' and 'str'"
    assert parsed_tb.frames == [{'source_line': 'print(add(1, "two"))',
                                 'source_line_anchor': '      ^^^^^^^^^^^^^',
                                 'filepath': 'main.py',
                                 'lineno': '3',
                                 'funcname': '<module>'},
                                {'source_line': 'return a + b',
                                 'source_line_anchor': '       ~~^~~',
                                 'filepath': 'add.py',
                                 'lineno': '2',
                                 'funcname': 'add'}]
    assert parsed_tb.to_string() == _ANCHOR_TB_STR


def test_parsed_exc_with_anchor_indented():
    """anchors stay aligned when the whole traceback arrives indented,
    e.g. pasted from a log: source_line is stripped, and the anchor is
    dedented by the same amount"""
    plain = ParsedException.from_string(_ANCHOR_TB_STR)
    indented = ParsedException.from_string(
        '\n'.join('    ' + line for line in _ANCHOR_TB_STR.splitlines()))
    assert indented.frames == plain.frames


def test_parsed_exc_truncated():
    """a traceback whose last frame has a source line but no following
    exception line should parse without raising IndexError"""
    _tb_str = """\
Traceback (most recent call last):
  File "main.py", line 3, in <module>
    print(add(1, 2))"""

    parsed_tb = ParsedException.from_string(_tb_str)

    assert parsed_tb.exc_type == ''
    assert parsed_tb.exc_msg == ''
    assert parsed_tb.frames == [{'source_line': 'print(add(1, 2))',
                                 'filepath': 'main.py',
                                 'lineno': '3',
                                 'funcname': '<module>'}]


# captured from CPython 3.14, which shows every row of a multiline expression
_MULTILINE_TB_STR = """\
Traceback (most recent call last):
  File "/tmp/tbcap/ml.py", line 6, in <module>
    f({})
    ~^^^^
  File "/tmp/tbcap/ml.py", line 2, in f
    y = x["b"
        ~^^^^
    ]
    ^
KeyError: 'b'"""


def test_parsed_exc_multiline_source():
    parsed_tb = ParsedException.from_string(_MULTILINE_TB_STR)

    assert parsed_tb.exc_type == 'KeyError'
    assert parsed_tb.exc_msg == "'b'"
    assert parsed_tb.frames[-1] == {'source_line': 'y = x["b"',
                                    'source_line_anchor': '    ~^^^^',
                                    'source_line_continuations': [']', '^'],
                                    'filepath': '/tmp/tbcap/ml.py',
                                    'lineno': '2',
                                    'funcname': 'f'}
    assert parsed_tb.to_string() == _MULTILINE_TB_STR

    indented = ParsedException.from_string(
        '\n'.join('    ' + line for line in _MULTILINE_TB_STR.splitlines()))
    assert indented.frames == parsed_tb.frames

def test_parsed_exc_source_file_and_dict():
    parsed = ParsedException('ValueError', 'bad', [{'filepath': 'a.py', 'lineno': '1',
                                                    'funcname': 'f', 'source_line': ''}])
    assert parsed.source_file == 'a.py'
    assert parsed.to_dict() == {'exc_type': 'ValueError', 'exc_msg': 'bad',
                                'frames': parsed.frames}
    assert repr(parsed).startswith("ParsedException('ValueError', 'bad', frames=")

    empty = ParsedException('KeyError', '')
    assert empty.source_file is None
    assert empty.frames == []


def test_parsed_exc_accepts_bytes():
    tb = (b'Traceback (most recent call last):\n'
          b'  File "b.py", line 3, in run\n'
          b'    boom()\n'
          b'RuntimeError: kaboom')
    parsed = ParsedException.from_string(tb)
    assert parsed.exc_type == 'RuntimeError'
    assert parsed.exc_msg == 'kaboom'
    assert parsed.frames == [{'source_line': 'boom()', 'filepath': 'b.py',
                              'lineno': '3', 'funcname': 'run'}]


def test_parsed_exc_ignores_trailing_ignored_exception():
    tb = ('Traceback (most recent call last):\n'
          '  File "c.py", line 1, in <module>\n'
          '    fail()\n'
          'OSError: disk on fire\n'
          'Exception ignored')
    parsed = ParsedException.from_string(tb)
    assert parsed.exc_type == 'OSError'
    assert parsed.exc_msg == 'disk on fire'
    assert len(parsed.frames) == 1


def test_parsed_exc_syntax_error_format():
    tb = ('  File "syntax.py", line 1\n'
          '    def broken(\n'
          '              ^\n'
          'SyntaxError: invalid syntax')
    parsed = ParsedException.from_string(tb)
    assert parsed.exc_type == 'SyntaxError'
    assert parsed.exc_msg == 'invalid syntax'
    assert parsed.frames == [{'source_line': 'def broken(',
                              'source_line_anchor': '          ^',
                              'filepath': 'syntax.py',
                              'lineno': '1'}]


def test_parsed_exc_unrecognized_raises():
    try:
        ParsedException.from_string('not a traceback at all')
    except ValueError as e:
        assert 'unrecognized traceback' in str(e)
    else:
        raise AssertionError('expected ValueError')


def test_parsed_exc_frame_without_following_line():
    tb = ('Traceback (most recent call last):\n'
          '  File "only.py", line 5, in last')
    parsed = ParsedException.from_string(tb)
    assert parsed.frames == [{'source_line': '', 'filepath': 'only.py',
                              'lineno': '5', 'funcname': 'last'}]
    assert parsed.exc_type == ''
    assert parsed.exc_msg == ''
