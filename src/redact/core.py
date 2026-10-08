"""Delete integer byte ranges from a file using a JSON scheme."""


def redact(data: bytes, scheme: object) -> bytes:
    """Delete [start, end) ranges measured in the original input bytes."""
    if not isinstance(scheme, dict) or set(scheme) != {"delete"}:
        raise ValueError('scheme must be an object containing only "delete"')
    raw_ranges = scheme["delete"]
    if not isinstance(raw_ranges, list):
        raise ValueError('"delete" must be a list of [start, end] byte ranges')

    ranges: list[tuple[int, int]] = []
    for index, span in enumerate(raw_ranges):
        if (
            not isinstance(span, list)
            or len(span) != 2
            or any(type(value) is not int for value in span)
        ):
            raise ValueError(f"delete[{index}] must be a pair of integers")
        start, end = span
        if not 0 <= start <= end <= len(data):
            raise ValueError(
                f"delete[{index}] must satisfy 0 <= start <= end <= {len(data)}"
            )
        ranges.append((start, end))

    parts: list[bytes] = []
    cursor = 0
    for start, end in sorted(ranges):
        if start > cursor:
            parts.append(data[cursor:start])
        # Count original bytes, including bytes already deleted by earlier ranges.
        cursor = max(cursor, end)
    parts.append(data[cursor:])
    return b"".join(parts)
