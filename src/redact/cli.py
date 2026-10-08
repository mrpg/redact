"""Command-line interfaces for redaction and scheme generation."""

import csv
import json
import os
import warnings
from typing import Optional, cast

import click

from redact.core import redact
from redact.scheme import generate_scheme

INPUT = click.Path(exists=True, dir_okay=False, allow_dash=True)
OUTPUT = click.Path(dir_okay=False, allow_dash=True)


def _read_bytes(path: str) -> bytes:
    with click.open_file(path, "rb") as stream:
        return cast(bytes, stream.read())


def _write_bytes(path: str, data: bytes) -> None:
    with click.open_file(path, "wb") as stream:
        stream.write(data)


@click.command(name="redact")
@click.version_option(package_name="redact")
@click.option(
    "--scheme",
    "-s",
    "scheme_path",
    required=True,
    type=INPUT,
    help="JSON deletion scheme (use - for standard input).",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    default="-",
    type=OUTPUT,
    show_default=True,
    help="Write redacted bytes to this file.",
)
@click.argument("input_path", type=INPUT, default="-")
def redact_cli(input_path: str, scheme_path: str, output_path: str) -> None:
    """Delete byte ranges from INPUT (default: standard input)."""
    if input_path == scheme_path == "-":
        raise click.UsageError("INPUT and --scheme cannot both read standard input")
    try:
        scheme = json.loads(_read_bytes(scheme_path).decode("utf-8"))
        result = redact(_read_bytes(input_path), scheme)
        _write_bytes(output_path, result)
    except (OSError, ValueError, UnicodeError) as error:
        raise click.ClickException(str(error)) from error


@click.command(name="redact-scheme")
@click.version_option(package_name="redact")
@click.option(
    "--column",
    "-c",
    "columns",
    multiple=True,
    required=True,
    metavar="NAME",
    help="CSV column to empty; repeat for more columns.",
)
@click.option(
    "--delimiter",
    "-d",
    help="CSV delimiter (detected by default).",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    default="-",
    type=OUTPUT,
    show_default=True,
    help="Write the JSON scheme to this file.",
)
@click.argument("input_path", type=INPUT, default="-")
def scheme_cli(
    input_path: str,
    output_path: str,
    columns: tuple[str, ...],
    delimiter: Optional[str],
) -> None:
    """Generate a scheme for CSV INPUT (default: standard input)."""
    try:
        if (
            input_path != "-"
            and output_path != "-"
            and os.path.exists(output_path)
            and os.path.samefile(input_path, output_path)
        ):
            raise ValueError("input CSV and output scheme must be different files")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            scheme = generate_scheme(_read_bytes(input_path), list(columns), delimiter)
        for warning in caught:
            click.echo(f"Warning: {warning.message}", err=True)
        _write_bytes(output_path, (json.dumps(scheme, indent=2) + "\n").encode())
    except (OSError, ValueError, UnicodeError, csv.Error) as error:
        raise click.ClickException(str(error)) from error
