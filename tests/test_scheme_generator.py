import csv
import io
import json
from itertools import product
from pathlib import Path

import pytest

from redact import generate_scheme, redact

EXAMPLE = Path(__file__).resolve().parent.parent / "example"


def test_example():
    data = (EXAMPLE / "in.csv").read_bytes()
    scheme = generate_scheme(data, ["name"])
    assert scheme == json.loads((EXAMPLE / "scheme.json").read_text())
    assert redact(data, scheme) == (EXAMPLE / "out.csv").read_bytes()


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_detect_delimiter_and_preserve_bytes(delimiter, newline):
    header = f"\ufeffid{delimiter}name{delimiter}value{newline}"
    source = (
        header
        + f'001{delimiter}"Éva{delimiter} ""E""{newline}Lo"{delimiter}0007{newline}'
        + newline
        + f"002{delimiter}Bob{delimiter}NaN"
    ).encode("utf-8")
    expected = (
        header
        + f'001{delimiter}""{delimiter}0007{newline}'
        + newline
        + f"002{delimiter}{delimiter}NaN"
    ).encode("utf-8")
    assert redact(source, generate_scheme(source, ["name"])) == expected


@pytest.mark.parametrize(
    "source,columns,expected",
    [
        (
            b'\r\n"id","full,\r\nname",value\r\n1,"A, B",0\r\n',
            ["full,\r\nname"],
            b'\r\n"id","full,\r\nname",value\r\n1,"",0\r\n',
        ),
        (
            b'id,name,name,value\n001,A,"B",02\n002,,"",03\n',
            ["name", "name"],
            b'id,name,name,value\n001,,"",02\n002,,"",03\n',
        ),
        (b"id,name,value\n001,A,02", ["value", "id"], b"id,name,value\n,A,"),
        (b"a,b\n1,2\n", ["a", "b"], b"a,b\n,\n"),
        (b"a,b\n", ["b"], b"a,b\n"),
        (b'a,b\r\n,""\r\n\r\n', ["a", "b"], b'a,b\r\n,""\r\n\r\n'),
        (b'name\n"A"\n""\n"B"', ["name"], b'name\n""\n""\n""'),
        (b"0,01\n001,02\n", ["01"], b"0,01\n001,\n"),
        (b'a,b\n a"b, x \n', ["a"], b"a,b\n, x \n"),
    ],
)
def test_named_columns(source, columns, expected):
    assert redact(source, generate_scheme(source, columns, delimiter=",")) == expected


def test_explicit_unicode_delimiter():
    source = "id§prénom§value\r\n001§Zoë🙂§001.20\r\n".encode()
    scheme = generate_scheme(source, ["prénom"], delimiter="§")
    expected = "id§prénom§value\r\n001§§001.20\r\n".encode()
    assert redact(source, scheme) == expected


@pytest.mark.parametrize("quoting", [csv.QUOTE_MINIMAL, csv.QUOTE_ALL])
def test_writer_generated_records(quoting):
    values = [
        "",
        "0",
        "001.2300",
        "NULL",
        "NaN",
        "é🙂",
        "a,b;|c\td",
        'a"b',
        "x\r\ny\nz\rr",
    ]
    header = ["a", "b", "keep"]
    rows = [[first, second, "001"] for first, second in product(values, repeat=2)]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, quoting=quoting, lineterminator="\r\n")
    writer.writerows([header, *rows])
    source = stream.getvalue().encode("utf-8")

    for columns in (["a"], ["b"], ["b", "a"], ["a", "b", "keep"]):
        scheme = generate_scheme(source, columns)
        result = redact(source, scheme).decode("utf-8")
        actual = list(csv.reader(io.StringIO(result, newline="")))
        expected = [header] + [
            ["" if name in columns else value for name, value in zip(header, row)]
            for row in rows
        ]
        assert actual == expected


@pytest.mark.parametrize(
    "source,columns,message",
    [
        (b"", ["a"], "no header"),
        (b"\r\n\n", ["a"], "no header"),
        (b"a,b\n1\n", ["b"], "expected 2 fields"),
        (b"a,b\n1,2,3\n", ["b"], "expected 2 fields"),
        (b'a,b\n1,"unfinished', ["b"], "unexpected end"),
        (b'a,b\n1,"value"junk\n', ["b"], "expected after"),
        (b"name\nAlice\n", ["name"], "single-column"),
        (b"name\nAlice", ["name"], "single-column"),
    ],
)
def test_invalid_input(source, columns, message):
    with pytest.raises((ValueError, csv.Error), match=message):
        generate_scheme(source, columns, delimiter=",")


def test_unknown_columns_warn():
    source = b"a,b\n1,2\n"
    with pytest.warns(UserWarning, match="unknown columns ignored: 'missing'"):
        scheme = generate_scheme(source, ["b", "missing"], delimiter=",")
    assert redact(source, scheme) == b"a,b\n1,\n"


@pytest.mark.parametrize("delimiter", ["", "::", '"', "\r", "\n"])
def test_invalid_delimiter(delimiter):
    with pytest.raises(ValueError, match="delimiter must"):
        generate_scheme(b"a,b\n1,2\n", ["b"], delimiter=delimiter)


def test_detection_failure_has_explicit_override():
    source = b'name\n"Alice"\n'
    with pytest.raises(ValueError, match="specify --delimiter"):
        generate_scheme(source, ["name"])
    scheme = generate_scheme(source, ["name"], delimiter=",")
    assert redact(source, scheme) == b'name\n""\n'
