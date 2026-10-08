# Byte-range redaction

`redact` deletes byte ranges from a file according to a JSON scheme.
`redact-scheme` generates a scheme that empties named columns in a UTF-8 CSV file.
Both commands read standard input by default and write standard output by default.

Install the commands with Python 3.12 or newer:

```sh
uv tool install .
```

Generate a scheme, then apply it:

```sh
redact-scheme -c name -o scheme.json in.csv
redact -s scheme.json -o out.csv in.csv
```

Use `-` explicitly for standard input or output. For example, the generator can
pipe its scheme directly to the redactor:

```sh
redact-scheme -c name in.csv | redact -s - in.csv > out.csv
```

Repeat `-c` to select more than one column. The generator detects comma,
semicolon, tab, or pipe delimiters; use `-d` when detection fails or the file
uses another delimiter:

```sh
redact-scheme -c name -c value -d ';' -o scheme.json in.csv
```

The first nonblank CSV record is the header and stays byte-for-byte intact.
Names match exactly; repeated header names select every matching column. The
generator handles UTF-8 with an optional BOM, double-quoted fields, doubled
quotes, embedded newlines, LF/CRLF/CR endings, blank lines, and a missing final
newline. Quoted values become `""`; unquoted values become empty. Other bytes
stay intact. Unknown columns, malformed CSV, and inconsistent row widths fail
before the output file is opened. Single-column values must already be quoted:
deleting an unquoted value would turn its line into a blank record.

The supplied `scheme.json` produces the supplied `out.csv` from `in.csv`:

```json
{
  "delete": [[16, 21], [27, 30], [35, 42], [51, 55]]
}
```

Each `[start, end]` deletes bytes from `start` up to but excluding `end`.
Positions are zero-based byte offsets in the original input. Overlapping or
repeated ranges delete their union, adjacent ranges work, and `[n, n]` does
nothing. The scheme must contain only `delete`, holding a list of integer pairs
satisfying `0 <= start <= end <= input length`. Invalid schemes fail before the
output file is opened. The redactor reads the full input before writing, so it
can write back to the input file. Both commands hold the input in memory.

The library exposes both operations:

```python
from redact import generate_scheme, redact

data = b"id,name\n1,Alice\n"
scheme = generate_scheme(data, ["name"])
result = redact(data, scheme)
assert result == b"id,name\n1,\n"
```

For development, `uv sync` installs the package and all test tools. Run checks
inside the managed environment with:

```sh
uv sync
uv run pytest
uv run black --check .
uv run ruff check .
uv run isort --check-only .
uv run mypy
uv build
```

Run `uv lock --upgrade` to refresh the lockfile to newer dependency releases.
