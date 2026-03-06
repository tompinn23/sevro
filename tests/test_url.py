from types import SimpleNamespace

from sevro import url


def test_parsing():
    parsed = url.parse("https://www.google.com")
    assert parsed.scheme() == "https"
    assert parsed.host() == "www.google.com"


def test_query_params():
    parsed = url.parse("/path?query=1&a=2&b=3&a=4")
    assert parsed.query_string() == "query=1&a=2&b=3&a=4"
    assert parsed.query() == {"query": ["1"], "a": ["2", "4"], "b": ["3"]}


def test_from_scope():
    parsed = url.from_scope(
        SimpleNamespace(
            server="127.0.0.1:80",
            scheme="https",
            path="/hello/world",
            query_string="a=2&b=1",
            headers={},
        )
    )
    assert parsed.scheme() == "https"
    assert parsed.host() == "127.0.0.1"
