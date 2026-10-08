"""Generate byte deletions for named CSV columns, keeping the header."""

import csv
import io
import warnings
from collections.abc import Iterator
from typing import Optional


def _field_spans(record: str, delimiter: str) -> Iterator[tuple[int, int]]:
    """Locate values, retaining outer quotes, in a validated CSV record."""
    position = 0
    while True:
        start = position
        if record[position : position + 1] == '"':
            position += 1
            while True:
                position = record.index('"', position) + 1
                if record[position : position + 1] != '"':
                    break
                position += 1  # A doubled quote belongs to the value.
            yield start + 1, position - 1
        else:
            while position < len(record) and record[position] not in (
                delimiter,
                "\r",
                "\n",
            ):
                position += 1
            yield start, position
        if record[position : position + 1] != delimiter:
            return
        position += 1


def generate_scheme(
    data: bytes, columns: list[str], delimiter: Optional[str] = None
) -> dict[str, list[list[int]]]:
    """Read UTF-8 CSV as strings and locate selected values in the original bytes."""
    text = data.decode("utf-8-sig")
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text, delimiters=",;\t|").delimiter
        except csv.Error as error:
            raise ValueError("cannot detect delimiter; specify --delimiter") from error
    if len(delimiter) != 1 or delimiter in '"\r\n':
        raise ValueError(
            "delimiter must be one character, excluding quotes and newlines"
        )
    stream = io.StringIO(text, newline="")
    reader = csv.reader(stream, delimiter=delimiter, strict=True)
    header = next((row for row in reader if row), [])
    if not header:
        raise ValueError("input has no header record")
    missing = set(columns) - set(header)
    if missing:
        warnings.warn(
            f"unknown columns ignored: {', '.join(map(repr, sorted(missing)))}",
            stacklevel=2,
        )
    selected = {index for index, name in enumerate(header) if name in columns}
    ranges: list[list[int]] = []
    character_cursor = stream.tell()
    byte_cursor = 3 if data.startswith(b"\xef\xbb\xbf") else 0
    byte_cursor += len(text[:character_cursor].encode("utf-8"))

    for row in reader:
        record_end = stream.tell()
        record = text[character_cursor:record_end]
        character_cursor = record_end
        if row and len(row) != len(header):
            raise ValueError(
                f"line {reader.line_num}: expected {len(header)} fields, got {len(row)}"
            )
        previous_end = 0
        spans = _field_spans(record, delimiter) if row else ()
        for index, (start, end) in enumerate(spans):
            if index not in selected or start == end:
                continue
            if len(header) == 1 and start == 0:
                raise ValueError(
                    "single-column values must be quoted: deletion alone would "
                    "turn an unquoted value into a blank CSV record"
                )
            byte_cursor += len(record[previous_end:start].encode("utf-8"))
            end_offset = byte_cursor + len(record[start:end].encode("utf-8"))
            ranges.append([byte_cursor, end_offset])
            byte_cursor = end_offset
            previous_end = end
        byte_cursor += len(record[previous_end:].encode("utf-8"))
    return {"delete": ranges}
