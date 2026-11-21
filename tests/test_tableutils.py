from boltons.tableutils import Table


def test_table_lists():
    data_lists = [['id', 'name'],
                  [1, 'John Doe'],
                  [2, 'Dale Simmons']]
    t1 = Table(data_lists)
    assert set(t1.headers) == {'id', 'name'}
    assert len(t1) == 2
    assert 'John Doe' in repr(t1)

T2_REF_HTML = """<table>
<tr><th>id</th><td>1</td></tr>
<tr><th>name</th><td>John Doe</td></tr>
</table>"""

T3_REF_HTML = """<table>
<thead>
<tr><th>id</th><th>name</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>John Doe</td></tr>
<tr><td>2</td><td>Dale Simmons</td></tr>
<tr><td>3</td><td>Kurt Rose</td></tr>
<tr><td>4</td><td>None</td></tr>
</tbody>
</table>"""


def test_table_dicts():
    data_dicts = [{'id': 1, 'name': 'John Doe'},
                  {'id': 2, 'name': 'Dale Simmons'}]
    t2 = Table.from_dict(data_dicts[0])
    t3 = Table.from_dict(data_dicts)
    t3.extend([[3, 'Kurt Rose'], [4]])

    assert set(t2.headers) == {'id', 'name'}
    assert len(t2) == 1
    # the sorted() stuff handles ordering differences between versions
    # TODO: should maybe change Table to sort the headers of dicts and such?
    assert sorted(t2.to_html()) == sorted(T2_REF_HTML)
    assert sorted(t3.to_html()) == sorted(T3_REF_HTML)
    assert t3.to_text()


def test_table_obj():
    class TestType:
        def __init__(self):
            self.greeting = 'hi'

    t4 = Table.from_object(TestType())
    assert len(t4) == 1
    assert 'greeting' in t4.headers



def test_to_text_empty_table():
    # used to raise ValueError from max() over an empty sequence
    assert Table([[]]).to_text() == ''


def test_to_text_none_headers():
    # used to raise AttributeError calling .center() on a None header
    t = Table([[None, 'b'], [1, 2]])
    lines = t.to_text().splitlines()
    header_cells = [c.strip() for c in lines[0].split(' | ')]
    # None headers render the same as None data cells
    assert header_cells[0] == 'None'


def test_to_text_no_headers():
    # used to raise IndexError; empty headers mean no header row or
    # separator rule, same as to_html
    t = Table([[], [1]])
    assert t.headers == []
    assert t.to_text() == '1'


def test_to_text_short_headers_padded():
    # used to raise IndexError; non-empty headers shorter than the
    # table width get padded with None cells, same as to_html
    t = Table([[1, 2]], headers=[])
    t.headers = ['a']
    lines = t.to_text().splitlines()
    header_cells = [c.strip() for c in lines[0].split(' | ')]
    assert header_cells == ['a', 'None']


def test_iterator_headers():
    # see #561
    t = Table([[1, 2]], headers=iter(['a', 'b']))
    assert t.headers == ['a', 'b']
    assert t.to_text().splitlines()[0] == 'a | b'

    t = Table.from_data([[1, 2]], headers=iter(['a', 'b']))
    assert t.headers == ['a', 'b']
    assert t.to_text().splitlines()[-1] == '1 | 2'


def test_headerless_extend_wider_row():
    # see #497
    t = Table([[1]], headers=[])
    t.extend([[2, 3]])
    assert t.to_text().splitlines() == ['1 | None', '2 |  3  ']


def test_to_html_bottom_metadata_after_table():
    # see #558
    t = Table([[1, 2]], headers=['a', 'b'], metadata={'k': 'v'})
    html = t.to_html(with_metadata='bottom')
    main_close = html.index('</table>')
    assert main_close < html.index('<br />') < html.index('<th>k</th>')
    assert html.endswith('</table>')
    assert html.count('<table>') == html.count('</table>') == 2

from collections import namedtuple

import pytest

from boltons.tableutils import (Table, InputType, ListInputType,
                                TupleInputType, NamedTupleInputType,
                                ObjectInputType, UnsupportedData,
                                escape_html, to_text)


class _BadStr:
    def __str__(self):
        raise ValueError('no str')

    def __repr__(self):
        return 'REPR_FALLBACK'


class _BadStrAndRepr:
    def __str__(self):
        raise ValueError('no str')

    def __repr__(self):
        raise ValueError('no repr')


class _BadProperty:
    def __init__(self):
        self.visible = 3

    @property
    def broken(self):
        raise AttributeError('property blows up')


def test_to_text_uses_str():
    assert to_text(12) == '12'


def test_to_text_falls_back_to_repr():
    assert to_text(_BadStr()) == 'REPR_FALLBACK'


def test_to_text_falls_back_to_object_repr():
    text = to_text(_BadStrAndRepr())
    assert text.startswith('<') and '_BadStrAndRepr' in text


def test_to_text_maxlen_truncates():
    assert to_text('abcdef', maxlen=5) == 'ab...'
    assert to_text('abc', maxlen=5) == 'abc'
    assert escape_html('a&b') == 'a&amp;b'


def test_input_type_default_get_entry_seq():
    class EchoInput(InputType):
        def get_entry(self, entry, headers):
            return list(entry)

    assert EchoInput().get_entry_seq([[1, 2], [3]], None) == [[1, 2], [3]]


def test_list_input_type_guess_headers_is_none():
    assert ListInputType().guess_headers([1, 2]) is None


def test_tuple_input_type():
    tit = TupleInputType()
    assert tit.check_type((1, 2))
    assert not tit.check_type([1, 2])
    assert tit.guess_headers((1, 2)) is None
    assert tit.get_entry((1, 2), None) == [1, 2]

    t = Table.from_data(((1, 2), (3, 4)))
    assert t.headers == []
    assert t._data == [[1, 2], [3, 4]]


def test_namedtuple_input_type():
    Point = namedtuple('Point', 'x y')
    p = Point(1, 2)
    nit = NamedTupleInputType()
    assert nit.check_type(p)
    assert nit.guess_headers(p) == ['x', 'y']
    assert nit.get_entry(p, ['x', 'y', 'z']) == [1, 2, None]

    t = Table.from_data([p])
    assert t.headers == ['x', 'y']
    assert t[0] == [1, 2]


def test_object_input_type_skips_raising_and_callables():
    obj = _BadProperty()
    oit = ObjectInputType()
    assert oit.check_type(obj)
    headers = oit.guess_headers(obj)
    assert 'visible' in headers
    assert 'broken' not in headers
    assert 'broken' not in headers  # raising property skipped

    t = Table.from_object(obj, headers=['visible', 'missing'])
    assert t[0] == [3, None]


def test_from_list_and_from_object():
    t = Table.from_list([[1, 2], [3, 4]])
    assert t.headers == []
    assert t[1] == [3, 4]

    t = Table.from_list([[1, 2]], headers=['a', 'b'])
    assert t.headers == ['a', 'b']
    assert t.to_text().splitlines()[0] == 'a | b'

    obj = _BadProperty()
    t = Table.from_object(obj, headers=['visible'])
    assert t[0] == [3]


def test_from_data_max_depth_zero_is_empty():
    t = Table.from_data([[1, 2]], headers=['a', 'b'], max_depth=0)
    assert len(t) == 0
    assert t.headers == ['a', 'b']


def test_from_data_empty_sequence():
    t = Table.from_data([])
    assert len(t) == 0
    t = Table.from_data([], headers=['a'])
    assert t.headers == ['a']
    assert len(t) == 0


def test_from_data_rewinds_when_first_element_unsupported():
    # first element is a DNR scalar (str), so Table falls back to
    # treating the whole list as the data sequence
    t = Table.from_data(['abc'])
    assert len(t) == 1
    assert t[0] == ['abc']
    assert t._width == 1


def test_from_data_scalar():
    t = Table.from_data(42)
    assert t.headers == [42]


def test_from_data_unsupported_raises():
    with pytest.raises(UnsupportedData):
        Table.from_data('abc')


def test_from_data_nested_tables():
    t = Table.from_data([[[1, 2]], [[3, 4]]], max_depth=2)
    assert isinstance(t[0][0], Table)
    assert t[0][0][0] == [1, 2]
    assert isinstance(t[1][0], Table)
    assert t[1][0][0] == [3, 4]


def test_getitem_and_repr():
    t = Table([[1, 2]], headers=None)
    assert t[0] == [1, 2]
    assert repr(t) == 'Table([[1, 2]])'
    t2 = Table([[1, 2]], headers=['a', 'b'])
    assert repr(t2) == "Table(headers=['a', 'b'], data=[[1, 2]])"


def test_extend_empty_is_noop():
    t = Table([[1]], headers=[])
    t.extend([])
    t.extend(None)
    assert t._data == [[1]]


def test_to_html_metadata_on_top():
    t = Table([[1, 2]], headers=['a', 'b'], metadata={'k': 'v'})
    html = t.to_html(with_metadata=True)
    assert html.count('<table>') == 2
    assert html.index('</table>') < html.index('<br />')
    assert '<th>k</th>' in html


def test_to_html_bad_orientation():
    t = Table([[1, 2]])
    with pytest.raises(ValueError):
        t.to_html(orientation='sideways')


def test_to_html_nested_horizontal():
    inner = Table([[1, 2]], headers=['a', 'b'])
    outer = Table([[inner, 'x'], ['y', 'z']], headers=['n', 'v'])
    html = outer.to_html(max_depth=2)
    assert html.count('<table>') == 2
    assert '<th>a</th>' in html


def test_to_html_nested_vertical():
    inner = Table([[1, 2]], headers=['a', 'b'])
    outer = Table([[inner, 'x']], headers=['n', 'v'])
    html = outer.to_html(orientation='v', max_depth=2)
    assert html.count('<table>') == 2
    assert '<th>a</th>' in html
    assert '<th>n</th>' in html and '<th>v</th>' in html
