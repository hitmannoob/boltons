import pytest

from boltons import urlutils
from boltons.urlutils import URL, QueryParamDict, _URL_RE, find_all_links


# fully quoted urls that should round trip
TEST_URLS = [
    'http://googlewebsite.com/e-shops.aspx',
    'http://example.com:8080/search?q=123&business=Nothing%20Special',
    'http://hatnote.com:9000?arg=1&arg=2&arg=3',
    'https://xn--bcher-kva.ch',
    'http://xn--ggbla1c4e.xn--ngbc5azd/',
    'http://tools.ietf.org/html/rfc3986#section-3.4',
    'http://wiki:pedia@hatnote.com',
    'ftp://ftp.rfc-editor.org/in-notes/tar/RFCs0001-0500.tar.gz',
    'http://[1080:0:0:0:8:800:200C:417A]/index.html',
    'ssh://192.0.2.16:2222/',
    'https://[::101.45.75.219]:80/?hi=bye',
    'ldap://[::192.9.5.5]/dc=example,dc=com??sub?(sn=Jensen)',
    'mailto:me@example.com?to=me@example.com&body=hi%20http://wikipedia.org',
    'news:alt.rec.motorcycle',
    'tel:+1-800-867-5309',
    'urn:oasis:member:A00024:x',
    ('magnet:?xt=urn:btih:1a42b9e04e122b97a5254e3df77ab3c4b7da725f&dn=Puppy%'
     '20Linux%20precise-5.7.1.iso&tr=udp://tracker.openbittorrent.com:80&'
     'tr=udp://tracker.publicbt.com:80&tr=udp://tracker.istole.it:6969&'
     'tr=udp://tracker.ccc.de:80&tr=udp://open.demonii.com:1337'),
    # from twisted:
    "http://localhost",
    "http://localhost/",
    "http://localhost/foo",
    "http://localhost/foo/",
    "http://localhost/foo!!bar/",
    "http://localhost/foo%20bar/",
    "http://localhost/foo%2Fbar/",
    "http://localhost/foo?n",
    "http://localhost/foo?n=v",
    "http://localhost/foo?n=/a/b",
    "http://example.com/foo!@$bar?b!@z=123",
    "http://localhost/asd?a=asd%20sdf/345",
    "http://(%2525)/(%2525)?(%2525)&(%2525)=(%2525)#(%2525)",
    "http://(%C3%A9)/(%C3%A9)?(%C3%A9)&(%C3%A9)=(%C3%A9)#(%C3%A9)"
    ]


@pytest.fixture(scope="module", params=TEST_URLS)
def test_url(request):
    param = request.param
    return param


def test_regex(test_url):
    match = _URL_RE.match(test_url)
    assert match.groupdict()


def test_roundtrip(test_url):
    result = URL(test_url).to_text(full_quote=True)
    assert test_url == result


def test_basic():
    u1 = URL('http://googlewebsite.com/e-shops.aspx')
    assert isinstance(u1.to_text(), str)
    assert u1.host == 'googlewebsite.com'


def test_utf8_url():
    url_bytes = (b'http://\xd9\x85\xd8\xab\xd8\xa7\xd9\x84'
                 b'.\xd8\xa2\xd8\xb2\xd9\x85\xd8\xa7'
                 b'\xdb\x8c\xd8\xb4\xdb\x8c')
    url = URL(url_bytes)
    assert url.scheme == 'http'
    assert url.host == 'مثال.آزمایشی'


def test_idna():
    u1 = URL('http://bücher.ch')
    assert u1.host == 'bücher.ch'
    assert u1.to_text(full_quote=True) == 'http://xn--bcher-kva.ch'
    assert u1.to_text(full_quote=False) == 'http://bücher.ch'

    u2 = URL('https://xn--bcher-kva.ch')
    assert u2.host == 'bücher.ch'
    assert u2.to_text(full_quote=True) == 'https://xn--bcher-kva.ch'
    assert u2.to_text(full_quote=False) == 'https://bücher.ch'


def test_query_params(test_url):
    url_obj = URL(test_url)
    if not url_obj.query_params or url_obj.fragment:
        return 
    qp_text = url_obj.query_params.to_text(full_quote=True)
    assert test_url.endswith(qp_text)


def test_parse_qsl_encoding():
    # %E9 is 'e' with an acute accent in latin-1, and not valid utf-8
    qs = 'k=%E9'
    assert urlutils.parse_qsl(qs, encoding='latin-1') == [('k', '\xe9')]
    # the default is unchanged: undecodable bytes become the replacement char
    assert urlutils.parse_qsl(qs) == [('k', '\ufffd')]
    # keys are decoded with the same encoding as values
    assert urlutils.parse_qsl('%E9=v', encoding='latin-1') == [('\xe9', 'v')]


def test_query_param_dict_eq_with_dict():
    qpd = QueryParamDict([('a', '1'), ('b', '2')])
    assert qpd == {'a': '1', 'b': '2'}
    assert qpd != {'a': '999', 'b': '2'}
    assert not (qpd == {'a': '999', 'b': '2'})


def test_iri_query():
    url = URL('http://minerals.mountain.ore/?rock=\N{SHAMROCK}')
    assert url.query_params['rock'] == '\N{SHAMROCK}'
    assert url.query_params.to_text(full_quote=True).endswith('%E2%98%98')


def test_iri_path():
    url = URL('http://minerals.mountain.ore/rock/\N{SHAMROCK}/')
    assert url.path == '/rock/\N{SHAMROCK}/'
    assert url.to_text(full_quote=True).endswith('%E2%98%98/')


def test_url_copy():
    url = URL('http://example.com/foo?bar=baz')
    url_copy = URL(url)
    assert url == url_copy


def test_invalid_port():
    with pytest.raises(ValueError):
        URL('http://reader.googlewebsite.com:neverforget')


def test_invalid_ipv6():
    invalid_ipv6_ips = ['2001::0234:C1ab::A0:aabc:003F',
                        '2001::1::3F']
    for ip in invalid_ipv6_ips:
        with pytest.raises(ValueError):
            URL('http://[' + ip + ']')


def test_parse_url():
    expected = {'family': 2, 'password': None, 'fragment': None,
                'authority': '127.0.0.1:3000', 'port': 3000, 'query': 'a=1',
                '_netloc_sep': '//', 'path': '/', 'scheme': 'http',
                'host': '127.0.0.1', 'username': None}
    res = urlutils.parse_url('http://127.0.0.1:3000/?a=1')
    assert res == expected


def test_parse_equals_in_qp_value():
    u = URL('http://localhost/?=x=x=x')
    assert u.qp[''] == 'x=x=x'
    assert u.to_text() == 'http://localhost/?=x%3Dx%3Dx'

    u = URL('http://localhost/?foo=x=x=x&bar=y')
    assert u.qp['foo'] == 'x=x=x'
    assert u.qp['bar'] == 'y'


def test_identical_equal():
    u = URL('http://example.com/path?query=param#frag')
    assert u == u


def test_equal():
    u = URL('http://example.com/path?query=param#frag')
    bono = URL('http://example.com/path?query=param#frag')
    assert bono == u


def test_not_equal():
    u = URL('http://example.com/path?query=param1#frag')
    bono = URL('http://example.com/path?query=param2#frag')
    assert bono != u


def _test_bad_utf8():  # not part of the API
    bad_bin_url = 'http://xn--9ca.com/%00%FF/%C3%A9'
    url = URL(bad_bin_url)

    expected = ('http://\N{LATIN SMALL LETTER E WITH ACUTE}.com/'
                '%00%FF/'
                '\N{LATIN SMALL LETTER E WITH ACUTE}')

    actual = url.to_text()

    assert expected == actual


def test_userinfo():
    url = URL('http://someuser:somepassword@example.com/some-segment@ignore')
    assert url.username == 'someuser'
    assert url.password == 'somepassword'
    assert url.to_text() == 'http://someuser:somepassword@example.com/some-segment@ignore'


def test_password_without_username():
    url = URL('http://:secret@example.com/path')
    assert url.to_text() == 'http://:secret@example.com/path'
    assert url.get_authority(with_userinfo=True) == ':secret@example.com'
    assert url.get_authority() == 'example.com'
    url.password = 'p@ss'
    assert url.to_text(full_quote=True) == 'http://:p%40ss@example.com/path'


def test_quoted_userinfo():
    url = URL('http://wikipedia.org')
    url.username = 'user'
    url.password = 'p@ss'
    assert url.to_text(full_quote=True) == 'http://user:p%40ss@wikipedia.org'

    url = URL('http://beyonc\xe9:b\xe9b@tmp.com')
    # assert url.to_text(full_quote=False) == u'http://beyoncé:b%C3%A9b@tmp.com'
    assert url.to_text(full_quote=True) == 'http://beyonc%C3%A9:b%C3%A9b@tmp.com'


def test_mailto():
    mt = 'mailto:mahmoud@hatnote.com'
    url = URL(mt)
    assert url.scheme == 'mailto'
    assert url.to_text() == mt


# Examples from RFC 3986 section 5.4, Reference Resolution Examples
# painstakingly copied from the lovingly transcribed version in
# twisted's test_url, with inapplicable cases removed
REL_URL_BASE = 'http://a/b/c/d;p?q'
REL_URL_TEST_CASES = [
    # "Normal"
    #('g:h', 'g:h'),     # Not supported:  scheme with relative path
    ('g', 'http://a/b/c/g'),
    ('./g', 'http://a/b/c/g'),
    ('g/', 'http://a/b/c/g/'),
    ('/g', 'http://a/g'),
    (';x', 'http://a/b/c/;x'),
    ('g;x', 'http://a/b/c/g;x'),
    ('', 'http://a/b/c/d;p?q'),
    ('.', 'http://a/b/c/'),
    ('./', 'http://a/b/c/'),
    ('..', 'http://a/b/'),
    ('../', 'http://a/b/'),
    ('../g', 'http://a/b/g'),
    ('../..', 'http://a/'),
    ('../../', 'http://a/'),
    ('../../g', 'http://a/g'),

    # Abnormal examples
    # ".." cannot be used to change the authority component of a URI.
    ('../../../g', 'http://a/g'),  # TODO (rooted?)
    ('../../../../g', 'http://a/g'),  # TODO (rooted)?

    # Only include "." and ".." when they are only part of a larger segment,
    # not by themselves.
    ('/./g', 'http://a/g'),
    ('/../g', 'http://a/g'),
    ('g.', 'http://a/b/c/g.'),
    ('.g', 'http://a/b/c/.g'),
    ('g..', 'http://a/b/c/g..'),
    ('..g', 'http://a/b/c/..g'),

    # Unnecessary or nonsensical forms of "." and "..".
    ('./../g', 'http://a/b/g'),
    ('./g/.', 'http://a/b/c/g/'),
    ('g/./h', 'http://a/b/c/g/h'),
    ('g/../h', 'http://a/b/c/h'),
    ('g;x=1/./y', 'http://a/b/c/g;x=1/y'),
    ('g;x=1/../y', 'http://a/b/c/y'),
]


def test_rel_navigate():
    for suffix, expected in REL_URL_TEST_CASES:
        url = URL(REL_URL_BASE)
        new_url = url.navigate(suffix)
        assert new_url.to_text() == expected

        new_url = url.navigate(URL(suffix))
        assert new_url.to_text() == expected

    return


def test_navigate():
    orig_text = 'http://a.b/c/d?e#f'
    orig = URL(orig_text)
    navd = orig.navigate('')
    # fragment removed on empty navigate
    assert navd.to_text() == 'http://a.b/c/d?e'

    # query also removed on non-empty navigate (interp'd as rel path)
    navd = orig.navigate('dd')
    assert navd.to_text() == 'http://a.b/c/dd'

    # check trailing slash
    navd = orig.navigate('dd/')
    assert navd.to_text() == 'http://a.b/c/dd/'

    # path removed on absolute path navigate
    navd = orig.navigate('/C')
    assert navd.to_text() == 'http://a.b/C'

    # only query string
    navd = orig.navigate('?e=E&ee=EE')
    assert navd.to_text() == 'http://a.b/c/d?e=E&ee=EE'

    # only fragment
    navd = orig.navigate('#FFF')
    assert navd.to_text() == 'http://a.b/c/d?e#FFF'

    # an odd case, bears more consideration perhaps
    navd = orig.navigate('https:')
    assert navd.to_text() == 'https://a.b/c/d?e'

    # another odd one, host only
    navd = orig.navigate('//newhost')
    assert navd.to_text() == 'http://newhost/c/d?e'

    # absolute URLs (with scheme + host) replace everything
    _dest_text = 'http://hatnote.com'
    _dest = URL(_dest_text)
    navd = orig.navigate(_dest)
    assert _dest is not navd  # make sure copies are made
    assert navd.to_text() == _dest_text
    navd = orig.navigate(_dest_text)
    assert navd.to_text() == _dest_text


def test_navigate_absolute_normalizes():
    url = URL('http://x.com')
    navd = url.navigate('HTTPS://EXAMPLE.ORG/a/./b/../c')
    assert navd.to_text() == 'https://example.org/a/c'

    dest = URL('HTTPS://EXAMPLE.ORG/a/./b/../c')
    navd = url.navigate(dest)
    assert navd.to_text() == 'https://example.org/a/c'
    assert dest.to_text() == 'HTTPS://EXAMPLE.ORG/a/./b/../c'  # input not mutated


def test_navigate_ipv6_keeps_brackets():
    url = URL('https://[::1]/a/b')
    assert url.navigate('child').to_text() == 'https://[::1]/a/child'
    assert url.navigate('//example.com/x').to_text() == 'https://example.com/x'


def test_port_zero_roundtrips():
    url = URL('http://example.com:0/path')
    assert url.port == 0
    assert url.to_text() == 'http://example.com:0/path'


def test_register_scheme_reclassify():
    scheme = 'boltons-test-reclassify'
    try:
        urlutils.register_scheme(scheme, uses_netloc=True, default_port=9999)
        urlutils.register_scheme(scheme, uses_netloc=False)
        assert scheme not in urlutils.SCHEME_PORT_MAP
        assert scheme in urlutils.NO_NETLOC_SCHEMES

        urlutils.register_scheme(scheme, uses_netloc=True, default_port=9998)
        assert urlutils.SCHEME_PORT_MAP[scheme] == 9998
        assert scheme not in urlutils.NO_NETLOC_SCHEMES
    finally:
        urlutils.SCHEME_PORT_MAP.pop(scheme, None)
        urlutils.NO_NETLOC_SCHEMES.discard(scheme)



@pytest.mark.parametrize(
    ('expected', 'base', 'paths'), [
    ('https://host/b', 'https://host', ('a', '/b', )),
    ('https://host/b', 'https://host', ('a', 'b', )),
    ('https://host/a/b', 'https://host', ('a/', 'b', )),
    ('https://host/b', 'https://host', ('/a', 'b', )),
    ('https://host/a/b', 'https://host/a/', (None, 'b', )),
    ('https://host/b', 'https://host/a', (None, 'b', )),
])
def test_chained_navigate(expected, base, paths):
    """Chained :meth:`navigate` calls produces correct results."""
    url = URL(base)

    for path in paths:
        url = url.navigate(path)

    assert expected == url.to_text()


# TODO: RFC3986 6.2.3 (not just for query add, either)
# def test_add_query():
#     url = URL('http://www.example.com')
#     url.qp['key'] = 'value'
#     assert url.to_text() == 'http://www.example.com/?key=value'


def test_self_normalize():
    url = URL('http://hatnote.com/a/../../b?k=v#hashtags')
    url.normalize()
    assert url.to_text() == 'http://hatnote.com/b?k=v#hashtags'


def test_normalize_with_case():
    # from RFC 3986 Section 6.2.2
    url1 = URL('example://a/b/c/%7Bfoo%7D')
    url2 = URL('eXAMPLE://a/./b/../b/%63/%7bfoo%7d')

    assert url1 != url2

    url1.normalize()
    url2.normalize()

    assert url1 == url2


def test_netloc_slashes():
    # basic sanity checks
    url = URL('mailto:mahmoud@hatnote.com')
    assert url.scheme == 'mailto'
    assert url.to_text() == 'mailto:mahmoud@hatnote.com'

    url = URL('http://hatnote.com')
    assert url.scheme == 'http'
    assert url.to_text() == 'http://hatnote.com'

    # test that unrecognized schemes stay consistent with '//'
    url = URL('newscheme:a:b:c')
    assert url.scheme == 'newscheme'
    assert url.to_text() == 'newscheme:a:b:c'

    url = URL('newerscheme://a/b/c')
    assert url.scheme == 'newerscheme'
    assert url.to_text() == 'newerscheme://a/b/c'

    # test that reasonable guesses are made
    url = URL('git+ftp://gitstub.biz/glyph/lefkowitz')
    assert url.scheme == 'git+ftp'
    assert url.to_text() == 'git+ftp://gitstub.biz/glyph/lefkowitz'

    url = URL('what+mailto:freerealestate@enotuniq.org')
    assert url.scheme == 'what+mailto'
    assert url.to_text() == 'what+mailto:freerealestate@enotuniq.org'

    url = URL()
    url.scheme = 'ztp'
    url.path = '/x/y/z'
    assert url.to_text() == 'ztp:/x/y/z'

    # also works when the input doesn't include '//'
    url = URL()
    url.scheme = 'git+ftp'
    url.path = '/x/y/z/'
    assert url.to_text() == 'git+ftp:///x/y/z/'

    # really why would this ever come up but ok
    url = URL('file:///path/to/heck')
    url.scheme = 'mailto'
    assert url.to_text() == 'mailto:/path/to/heck'

    return


# (link_text, expected_urls)
# adapted from tornado test suite
FAL_TESTS = [("hello http://world.com/!", ["http://world.com/"]),
             ("hello http://world.com/with?param=true&stuff=yes", ["http://world.com/with?param=true&stuff=yes"]),
             ("http://url.com/w(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", ["http://url.com/w"]),
             ("http://url.com/withmany.......................................", ["http://url.com/withmany"]),
             ("http://url.com/withmany((((((((((((((((((((((((((((((((((a)", ["http://url.com/withmany"]),
             # some examples from http://daringfireball.net/2009/11/liberal_regex_for_matching_urls
             ("http://foo.com/blah_blah", ["http://foo.com/blah_blah"]),
             ("http://foo.com/blah_blah/", ["http://foo.com/blah_blah/"]),
             ("(Something like http://foo.com/blah_blah)", ["http://foo.com/blah_blah"]),
             ("http://foo.com/blah_blah_(wikipedia)", ["http://foo.com/blah_blah_(wikipedia)"]),
             ("http://foo.com/blah_(blah)_(wikipedia)_blah", ["http://foo.com/blah_(blah)_(wikipedia)_blah"]),
             ("http://foo.com/blah_blah.", ["http://foo.com/blah_blah"]),
             ("http://foo.com/blah_blah/.", ["http://foo.com/blah_blah/"]),
             ("<http://foo.com/blah_blah>", ["http://foo.com/blah_blah"]),
             ("<http://foo.com/blah_blah/>", ["http://foo.com/blah_blah/"]),
             ("http://foo.com/blah_blah,", ["http://foo.com/blah_blah"]),
             ("http://www.example.com/wpstyle/?p=364.", ["http://www.example.com/wpstyle/?p=364"]),
             ("rdar://1234", ["rdar://1234"]),
             ("rdar:/1234", ["rdar:/1234"]),
             ("http://userid:password@example.com:8080", ["http://userid:password@example.com:8080"]),
             ("http://userid@example.com", ["http://userid@example.com"]),
             ("message://%3c330e7f8409726r6a4ba78dkf1fd71420c1bf6ff@mail.gmail.com%3e", ["message://%3C330e7f8409726r6a4ba78dkf1fd71420c1bf6ff@mail.gmail.com%3e"]),
             ("http://\u27a1.ws/\u4a39", ["http://\u27a1.ws/\u4a39"]),
             ("<tag>http://example.com</tag>", ["http://example.com"]),
             ("Just a www.example.com link.", ["https://www.example.com"]),
             ("www.a-link.com", ["https://www.a-link.com"]),
             ("www.a-link.com and www.b-link.com/blogs extra", ["https://www.a-link.com", "https://www.b-link.com/blogs"])
]


def test_find_all_links_basic():
    target = """hi my name is prince nigeria, please visit my website
    http://richprince.biz or if that's blocked try
    https://getprince.ly! Thanks for your attention.bye!

    PS if those ports are blocked, how about trying
    https://crownbux.afamilycompany:broken/affiliate

    PPS if all else fails you can always mailto:thePrince@machovelli.an
    """

    urls = find_all_links(target)
    assert len(urls) == 2


def test_find_all_links():
    prefix = "a little something before, "
    suffix = " a bit of another after."

    for content, expected_links in FAL_TESTS:
        text = prefix + content + suffix

        links = find_all_links(text)
        assert len(links) == len(expected_links)

        for link, expected in zip(links, expected_links):
            assert link.to_text(full_quote=False) == expected

        link_tokens = find_all_links(text, with_text=True)
        assert link_tokens[0].startswith(prefix)
        assert link_tokens[-1].endswith(suffix)


def test_find_all_links_rejected_without_text():
    text = 'http://example.com and https://example.org'
    links = find_all_links(text, schemes=['https'], with_text=False)
    assert links == [URL('https://example.org')]

    links = find_all_links('see www.example.com', default_scheme=False)
    assert links == []

    # with_text still keeps the rejected URL as text
    tokens = find_all_links(text, schemes=['https'], with_text=True)
    assert tokens[0] == 'http://example.com'
    assert tokens[-1] == URL('https://example.org')


def test_unicodey():
    unicodey = ('http://\N{LATIN SMALL LETTER E WITH ACUTE}.com/'
                '\N{LATIN SMALL LETTER E}\N{COMBINING ACUTE ACCENT}'
                '?\N{LATIN SMALL LETTER A}\N{COMBINING ACUTE ACCENT}='
                '\N{LATIN SMALL LETTER I}\N{COMBINING ACUTE ACCENT}'
                '#\N{LATIN SMALL LETTER U}\N{COMBINING ACUTE ACCENT}')
    url = URL(unicodey)
    assert url.host == 'é.com'
    assert url.path_parts[1] == '\N{LATIN SMALL LETTER E}\N{COMBINING ACUTE ACCENT}'
    assert url.to_text(full_quote=False) == unicodey
    fully_quoted = 'http://xn--9ca.com/%C3%A9?%C3%A1=%C3%AD#%C3%BA'
    assert url.to_text(full_quote=True) == fully_quoted

def test_str_repr():
    assert str(URL("http://googlewebsite.com/e-shops.aspx")) == "http://googlewebsite.com/e-shops.aspx"


def test_quote_part_non_full_quote():
    assert urlutils.quote_path_part('a b/c?d', full_quote=False) == 'a b%2Fc%3Fd'
    assert urlutils.quote_query_part('a b&c=d', full_quote=False) == 'a b%26c%3Dd'
    assert urlutils.quote_fragment_part('x y#z', full_quote=False) == 'x y%23z'
    assert urlutils.quote_userinfo_part('u ser@:x', full_quote=False) == 'u ser%40%3Ax'


def test_quote_part_full_quote():
    assert urlutils.quote_path_part('a b') == 'a%20b'
    assert urlutils.quote_query_part('a&b') == 'a%26b'
    assert urlutils.quote_fragment_part('a#b') == 'a%23b'
    assert urlutils.quote_userinfo_part('a@b') == 'a%40b'


def test_unquote_defaults_and_errors():
    assert urlutils.unquote('abc%20def') == 'abc def'
    assert urlutils.unquote('%E9', encoding=None) == '\ufffd'
    assert urlutils.unquote('%E9', errors=None) == '\ufffd'
    assert urlutils.unquote('no-escapes') == 'no-escapes'


def test_unquote_to_bytes_edges():
    assert urlutils.unquote_to_bytes('') == b''
    assert urlutils.unquote_to_bytes('abc') == b'abc'
    assert urlutils.unquote_to_bytes('a%20b') == b'a b'
    assert urlutils.unquote_to_bytes('abc%zzdef') == b'abc%zzdef'


def test_to_unicode_falls_back_to_decoding():
    class UndecodableStr(bytes):
        def __str__(self):
            raise UnicodeDecodeError('utf8', b'x', 0, 1, 'boom')

    assert urlutils.to_unicode(UndecodableStr(b'hi')) == 'hi'
    assert urlutils.to_unicode(5) == '5'


def test_register_scheme_validation():
    with pytest.raises(ValueError):
        urlutils.register_scheme('boltons-bad-port', default_port='notaport')
    with pytest.raises(ValueError):
        urlutils.register_scheme('boltons-bad-netloc', uses_netloc=False,
                                 default_port=80)
    with pytest.raises(ValueError):
        urlutils.register_scheme('boltons-bad-flag', uses_netloc='yes')

    assert urlutils.register_scheme('boltons-noop') is None
    assert 'boltons-noop' not in urlutils.SCHEME_PORT_MAP


def test_cachedproperty_class_access_and_repr():
    descriptor = URL.__dict__['query_params']
    assert descriptor.__get__(None) is descriptor
    assert repr(descriptor).startswith('<cachedproperty func=')

    url = URL('http://example.com/?a=1')
    assert url.query_params is url.query_params
    del url.__dict__['query_params']
    assert url.query_params == {'a': '1'}


def test_url_from_invalid_utf8_bytes():
    with pytest.raises(urlutils.URLParseError):
        URL(b'http://\xff.example.com')


def test_default_port_plus_heuristic():
    assert URL('http://example.com').default_port == 80
    assert URL('git+ftp://example.com/x').default_port == 21
    assert URL('unknownscheme://example.com').default_port is None


def test_url_repr_str_and_unicode():
    url = URL('http://example.com/a?b=1#c')
    assert repr(url) == "URL('http://example.com/a?b=1#c')"
    assert str(url) == 'http://example.com/a?b=1#c'
    assert url.__unicode__() == 'http://example.com/a?b=1#c'


def test_find_all_links_text_merging():
    assert find_all_links('http://a.com tail', schemes=['https'],
                          with_text=True) == ['http://a.com tail']
    assert find_all_links('see www.example.com now', default_scheme=False,
                          with_text=True) == ['see www.example.com now']
    tokens = find_all_links('visit http://x.com:bad/p now', with_text=True)
    assert tokens == ['visit http://x.com:bad/p now']

    tokens = find_all_links('http://a.com and https://b.com', schemes=['https'],
                            with_text=True)
    assert tokens[0] == 'http://a.com'
    assert tokens[1] == ' and '
    assert tokens[2] == URL('https://b.com')


def test_parse_qsl_keep_blank_values():
    assert urlutils.parse_qsl('a=&b=2') == [('a', None), ('b', '2')]
    assert urlutils.parse_qsl('a=&b=2', keep_blank_values=False) == [('b', '2')]
    assert urlutils.parse_qsl('&&') == []


def test_parse_host_and_port_edges():
    import socket as socket_module

    assert urlutils.parse_host('') == (None, '')
    assert urlutils.parse_host('example.com') == (None, 'example.com')
    assert urlutils.parse_host('192.168.1.1') == (
        socket_module.AF_INET, '192.168.1.1')
    assert urlutils.parse_host('[::1]') == (socket_module.AF_INET6, '::1')
    with pytest.raises(urlutils.URLParseError):
        urlutils.parse_host('[zz::1]')

    assert urlutils.parse_url('http://example.com:')['port'] is None
    assert urlutils.parse_url('http://example.com:8080/x')['port'] == 8080
    ipv6 = urlutils.parse_url('http://[::1]:8080/x')
    assert ipv6['host'] == '::1'
    assert ipv6['port'] == 8080
    assert ipv6['family'] == socket_module.AF_INET6


def test_get_authority_variants():
    url = URL('ftp://user:pass@ftp.debian.org:2121/debian/README')
    assert url.get_authority() == 'ftp.debian.org:2121'
    assert url.get_authority(with_userinfo=True) == 'user:pass@ftp.debian.org:2121'
    assert URL('http://bücher.ch').get_authority(full_quote=True) == 'xn--bcher-kva.ch'


def test_to_text_composition():
    assert URL().to_text() == ''
    assert URL.from_parts(scheme='http').to_text() == 'http://'
    assert URL.from_parts(scheme='http', path_parts=('', 'x')).to_text() == 'http:///x'
    assert URL.from_parts(path_parts=('a', 'b')).to_text() == 'a/b'
    assert URL.from_parts(fragment='a b#c').to_text(full_quote=False) == '#a b%23c'


def _load_fallback_urlutils():
    import importlib.util
    import sys

    from boltons import urlutils as real_urlutils
    name = 'boltons._urlutils_fallback_under_test'
    spec = importlib.util.spec_from_file_location(name, real_urlutils.__file__)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    blocked = ('boltons.dictutils', 'boltons.typeutils')
    saved = {n: sys.modules.get(n) for n in blocked}
    for n in blocked:
        sys.modules[n] = None
    try:
        spec.loader.exec_module(mod)
    finally:
        for n, value in saved.items():
            if value is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = value
    return mod


@pytest.fixture(scope='module')
def fallback_urlutils():
    return _load_fallback_urlutils()


def test_fallback_omd_basic(fallback_urlutils):
    OMD = fallback_urlutils.OrderedMultiDict
    omd = OMD([('a', 1), ('b', 2), ('a', 3)])
    assert omd['a'] == 3
    assert omd.get('a') == 3
    assert omd.get('missing') is None
    assert omd.get('missing', 9) == 9
    assert omd.getlist('a') == [1, 3]
    assert omd.getlist('missing') == []
    assert omd.getlist('missing', ['d']) == ['d']
    assert omd.keys() == ['a', 'b']
    assert omd.keys(multi=True) == ['a', 'b', 'a']
    assert omd.values() == [3, 2]
    assert omd.values(multi=True) == [1, 2, 3]
    assert omd.items() == [('a', 3), ('b', 2)]
    assert omd.items(multi=True) == [('a', 1), ('b', 2), ('a', 3)]
    assert list(omd) == ['a', 'b']
    assert list(reversed(omd)) == ['b', 'a']
    assert omd.todict() == {'a': 3, 'b': 2}
    assert omd.todict(multi=True) == {'a': [1, 3], 'b': [2]}
    assert omd.counts().todict() == {'a': 2, 'b': 1}
    assert repr(omd) == "OrderedMultiDict([('a', 1), ('b', 2), ('a', 3)])"
    assert OMD([(0, 2), (1, 2)]).inverted().getlist(2) == [0, 1]
    assert OMD(b=2)['b'] == 2


def test_fallback_omd_mutation(fallback_urlutils):
    OMD = fallback_urlutils.OrderedMultiDict
    omd = OMD()
    omd.add('a', 1)
    omd.addlist('a', [2, 3])
    omd.addlist('b', iter([4, 5]))
    omd.addlist('empty', [])
    assert omd.getlist('a') == [1, 2, 3]
    assert omd.getlist('b') == [4, 5]
    assert 'empty' not in omd

    assert omd.setdefault('c') is None
    assert omd['c'] is None
    assert omd.setdefault('d', 7) == 7
    assert omd.setdefault('d', 9) == 7

    assert omd.pop('a') == 3
    assert omd.getlist('a') == []
    assert omd.pop('a', 'fallback') == 'fallback'
    with pytest.raises(KeyError):
        omd.pop('a')
    assert omd.popall('b') == [4, 5]
    assert omd.popall('b', []) == []

    omd.add('z', 1)
    omd.add('z', 2)
    assert omd.poplast('z') == 2
    assert omd.getlist('z') == [1]
    assert omd.poplast('z') == 1
    assert 'z' not in omd
    with pytest.raises(KeyError):
        omd.poplast('z')
    assert omd.poplast('z', 'fallback') == 'fallback'

    ordered = OMD([('a', 1), ('b', 2)])
    assert ordered.poplast() == 2
    assert ordered.poplast() == 1
    with pytest.raises(KeyError):
        ordered.poplast()
    assert OMD().poplast(default='empty') == 'empty'


def test_fallback_omd_copy_update(fallback_urlutils):
    OMD = fallback_urlutils.OrderedMultiDict
    omd = OMD([('a', 1), ('b', 2), ('a', 3)])
    copied = omd.copy()
    assert copied == omd
    assert copied is not omd
    assert OMD.fromkeys(['x', 'y']) == OMD([('x', None), ('y', None)])
    assert OMD.fromkeys(['x'], 0) == OMD([('x', 0)])

    omd.update(omd)
    assert omd.items(multi=True) == [('a', 1), ('b', 2), ('a', 3)]
    omd.update(OMD([('a', 9)]))
    assert omd.getlist('a') == [9]
    omd.update({'b': 5})
    assert omd.getlist('b') == [5]
    omd.update([('c', 1), ('c', 2)])
    assert omd.getlist('c') == [1, 2]
    omd.update([('d', 1)], d=2, e=3)
    assert omd['d'] == 2
    assert omd['e'] == 3

    existing = OMD([('a', 1)])
    existing.update([('a', 2)])
    assert existing.getlist('a') == [2]

    extended = OMD([('a', 1)])
    extended.update_extend(extended)
    extended.update_extend(OMD([('a', 2)]))
    extended.update_extend({'a': 3})
    extended.update_extend([('a', 4)])
    assert extended.getlist('a') == [1, 1, 2, 3, 4]


def test_fallback_omd_equality(fallback_urlutils):
    OMD = fallback_urlutils.OrderedMultiDict
    omd = OMD([('x', 1), ('y', 2)])
    assert omd == omd
    assert omd == OMD([('x', 1), ('y', 2)])
    assert not (omd != OMD([('x', 1), ('y', 2)]))
    assert omd == {'x': 1, 'y': 2}
    assert (omd == {'x': 1, 'z': 2}) is False
    assert (omd == {'x': 9, 'y': 2}) is False
    assert (omd == {'x': 1}) is False
    assert (omd == [1, 2]) is False
    assert (omd == 5) is False
    assert (omd == OMD([('x', 1)])) is False
    assert (omd == OMD([('x', 1), ('z', 2)])) is False
    assert (omd == OMD([('x', 1), ('y', 2), ('y', 2)])) is False


def test_fallback_omd_state_item_and_views(fallback_urlutils):
    OMD = fallback_urlutils.OrderedMultiDict
    omd = OMD([('a', 1), ('a', 2), ('b', 3)])
    assert omd.__getstate__() == [('a', 1), ('a', 2), ('b', 3)]
    restored = OMD()
    restored.__setstate__(omd.__getstate__())
    assert restored == omd

    omd['a'] = 9
    assert omd.getlist('a') == [9]
    del omd['a']
    assert 'a' not in omd

    other = OMD([('a', 1)])
    other |= {'a': 2, 'b': 3}
    assert other['a'] == 2
    assert other['b'] == 3

    assert set(omd.viewkeys()) == {'b'}
    assert list(omd.viewvalues()) == [3]
    assert list(omd.viewitems()) == [('b', 3)]

    with pytest.raises(TypeError):
        OMD([('a', 1)], [('b', 2)])


def test_fallback_omd_sorted_and_clear(fallback_urlutils):
    OMD = fallback_urlutils.OrderedMultiDict
    omd = OMD(zip(range(3), range(3)))
    assert omd.sorted(reverse=True) == OMD([(2, 2), (1, 1), (0, 0)])

    values = OMD([('even', 6), ('odd', 1), ('even', 2),
                  ('odd', 5), ('even', 4), ('odd', 3)])
    sorted_values = values.sortedvalues()
    assert sorted_values.getlist('even') == [2, 4, 6]
    assert sorted_values.getlist('odd') == [1, 3, 5]
    assert sorted_values.keys(multi=True) == values.keys(multi=True)
    assert sorted_values != values

    values.clear()
    assert values == OMD()
    assert values.items() == []


def test_fallback_query_param_dict(fallback_urlutils):
    QueryParamDict = fallback_urlutils.QueryParamDict
    qpd = QueryParamDict.from_text('a=1&a=2&b=')
    assert qpd.getlist('a') == ['1', '2']
    assert qpd['b'] is None
    assert qpd.to_text() == 'a=1&a=2&b'
    assert qpd.to_text(full_quote=True) == 'a=1&a=2&b'

    quoted = QueryParamDict([('k', 'a b&c')])
    assert quoted.to_text() == 'k=a b%26c'
    assert quoted.to_text(full_quote=True) == 'k=a%20b%26c'

    url = fallback_urlutils.URL('http://example.com/p?x=1&x=2#frag')
    assert url.query_params.getlist('x') == ['1', '2']
    assert url.to_text() == 'http://example.com/p?x=1&x=2#frag'
