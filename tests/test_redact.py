from itertools import product

import pytest

from redact import redact


@pytest.mark.parametrize(
    "data,ranges,expected",
    [
        (b"", [], b""),
        (b"", [[0, 0]], b""),
        (b"abcdef", [], b"abcdef"),
        (b"abcdef", [[1, 3]], b"adef"),
        (b"abcdef", [[4, 5], [1, 3]], b"adf"),
        (b"abcdef", [[1, 4], [2, 5], [1, 4]], b"af"),
        (b"abcdef", [[1, 3], [3, 5]], b"af"),
        (b"abcdef", [[1, 5], [2, 3], [3, 3]], b"af"),
        (b"abcdef", [[0, 1], [5, 6]], b"bcde"),
        (b"abcdef", [[0, 6]], b""),
        (b"abcdef", [[0, 0], [3, 3], [6, 6]], b"abcdef"),
        (b"a,b\r\nc,d\r\n", [[0, 5]], b"c,d\r\n"),
        (b"one,two\n", [[3, 4]], b"onetwo\n"),
        (b"\x00\xff\x80\r\n", [[1, 2]], b"\x00\x80\r\n"),
        (
            b'\xef\xbb\xbf0,\xc3\xa9,"line\r\nbreak"\r\n',
            [[5, 7]],
            b'\xef\xbb\xbf0,,"line\r\nbreak"\r\n',
        ),
    ],
)
def test_redact(data, ranges, expected):
    assert redact(data, {"delete": ranges}) == expected


def test_all_pairs_of_small_ranges():
    """Compare every pair/order of small ranges with an independent byte filter."""
    for size in range(8):
        data = bytes(range(size))
        ranges = [
            [start, end] for start in range(size + 1) for end in range(start, size + 1)
        ]
        for spans in product(ranges, repeat=2):
            expected = bytes(
                value
                for position, value in enumerate(data)
                if not any(start <= position < end for start, end in spans)
            )
            assert redact(data, {"delete": list(spans)}) == expected, (size, spans)


@pytest.mark.parametrize(
    "scheme",
    [
        None,
        [],
        {},
        {"remove": []},
        {"delete": [], "extra": []},
        {"delete": None},
        {"delete": "0:1"},
        {"delete": {}},
        {"delete": [None]},
        {"delete": [1]},
        {"delete": [[]]},
        {"delete": [[0]]},
        {"delete": [[0, 1, 2]]},
        {"delete": [["0", 1]]},
        {"delete": [[0, "1"]]},
        {"delete": [[0.0, 1]]},
        {"delete": [[0, 1.0]]},
        {"delete": [[False, 1]]},
        {"delete": [[0, True]]},
        {"delete": [[None, 1]]},
        {"delete": [[-1, 1]]},
        {"delete": [[0, -1]]},
        {"delete": [[2, 1]]},
        {"delete": [[0, 4]]},
        {"delete": [[4, 4]]},
        {"delete": [[0, 1], [2, 4]]},
    ],
)
def test_invalid_scheme(scheme):
    with pytest.raises(ValueError):
        redact(b"abc", scheme)
