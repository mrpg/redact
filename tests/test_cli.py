"""Exercise the installed commands and their file-handling contracts."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from redact import redact
from redact.cli import redact_cli, scheme_cli

EXAMPLE = Path(__file__).resolve().parent.parent / "example"
BIN = Path(sys.executable).parent


def test_installed_commands_pipe_a_scheme() -> None:
    generated = subprocess.run(
        [str(BIN / "redact-scheme"), "-c", "name", str(EXAMPLE / "in.csv")],
        capture_output=True,
        check=True,
    )
    applied = subprocess.run(
        [str(BIN / "redact"), "-s", "-", str(EXAMPLE / "in.csv")],
        input=generated.stdout,
        capture_output=True,
        check=True,
    )
    assert applied.stdout == (EXAMPLE / "out.csv").read_bytes()


def test_commands_filter_standard_input_and_output(tmp_path: Path) -> None:
    source = b"id,name\n1,Alice\n"
    runner = CliRunner()
    generated = runner.invoke(scheme_cli, ["-c", "name", "-d", ","], input=source)
    assert generated.exit_code == 0, generated.output

    scheme_path = tmp_path / "scheme.json"
    scheme_path.write_bytes(generated.stdout_bytes)
    applied = runner.invoke(redact_cli, ["-s", str(scheme_path)], input=source)
    assert applied.exit_code == 0, applied.output
    assert applied.stdout_bytes == b"id,name\n1,\n"


def test_generator_writes_multiple_selected_columns(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    original = b"id;name;value\r\n001;Alice;0007\r\n"
    source.write_bytes(original)
    output = tmp_path / "scheme.json"

    result = CliRunner().invoke(
        scheme_cli,
        ["-c", "name", "-c", "value", "-d", ";", "-o", str(output), str(source)],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout_bytes == b""
    assert redact(original, json.loads(output.read_text(encoding="utf-8"))) == (
        b"id;name;value\r\n001;;\r\n"
    )


@pytest.mark.parametrize("scheme_text", [b'{"delete":', b'{"delete": [[0, 4]]}'])
@pytest.mark.parametrize("existing_output", [False, True])
def test_invalid_scheme_preserves_output(
    tmp_path: Path, scheme_text: bytes, existing_output: bool
) -> None:
    source = tmp_path / "input"
    source.write_bytes(b"abc")
    scheme = tmp_path / "scheme.json"
    scheme.write_bytes(scheme_text)
    output = tmp_path / "output"
    if existing_output:
        output.write_bytes(b"keep me")

    result = CliRunner().invoke(
        redact_cli, ["-s", str(scheme), "-o", str(output), str(source)]
    )
    assert result.exit_code == 1
    assert "Error:" in result.output
    if existing_output:
        assert output.read_bytes() == b"keep me"
    else:
        assert not output.exists()
    assert source.read_bytes() == b"abc"


@pytest.mark.parametrize("column", ["missing", "name"])
def test_invalid_csv_preserves_output(tmp_path: Path, column: str) -> None:
    source = tmp_path / "input.csv"
    original = b'id,name\n0,Alice\n1,"unfinished'
    source.write_bytes(original)
    output = tmp_path / "scheme.json"
    output.write_bytes(b"keep me")

    result = CliRunner().invoke(
        scheme_cli,
        ["-c", column, "-d", ",", "-o", str(output), str(source)],
    )
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert output.read_bytes() == b"keep me"
    assert source.read_bytes() == original


def test_redact_can_replace_input(tmp_path: Path) -> None:
    source = tmp_path / "input"
    source.write_bytes(b"abcdef")
    scheme = tmp_path / "scheme.json"
    scheme.write_text(json.dumps({"delete": [[4, 5], [1, 3]]}), encoding="utf-8")

    result = CliRunner().invoke(
        redact_cli, ["-s", str(scheme), "-o", str(source), str(source)]
    )
    assert result.exit_code == 0, result.output
    assert source.read_bytes() == b"adf"


def test_generator_refuses_to_replace_input(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    original = b"id,name\n1,Alice\n"
    source.write_bytes(original)

    result = CliRunner().invoke(
        scheme_cli, ["-c", "name", "-d", ",", "-o", str(source), str(source)]
    )
    assert result.exit_code == 1
    assert "different files" in result.output
    assert source.read_bytes() == original


def test_both_inputs_cannot_read_standard_input() -> None:
    result = CliRunner().invoke(redact_cli, ["-s", "-"])
    assert result.exit_code == 2
    assert "cannot both read standard input" in result.output


def test_unknown_columns_warn_on_stderr(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    source.write_bytes(b"id,name\n0,Alice\n")

    result = CliRunner().invoke(
        scheme_cli, ["-c", "name", "-c", "missing", "-d", ",", str(source)]
    )
    assert result.exit_code == 0
    assert result.stderr == "Warning: unknown columns ignored: 'missing'\n"
    assert json.loads(result.stdout) == {"delete": [[10, 15]]}
