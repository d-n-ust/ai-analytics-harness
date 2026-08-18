"""CLI: pure formatters, the exit-code rule, and an end-to-end scan on a semantic-only env."""

import json

from preflight.cli import build_parser, exit_code, format_json, format_text, main
from preflight.model import Finding, Item

_HIGH = Finding("SCOPE_TRAP", "high", "silently scoped", (Item("sl:a", "a", "semantic"),))
_LOW = Finding("NAME_COLLISION", "low", "reads alike", (Item("wh:b", "b", "warehouse"),))


def test_exit_code_thresholds():
    assert exit_code([_HIGH], "high") == 1
    assert exit_code([_LOW], "high") == 0        # low does not trip a high gate
    assert exit_code([_LOW], "low") == 1
    assert exit_code([_HIGH], "none") == 0       # never fail
    assert exit_code([], "high") == 0


def test_format_json_is_the_wire_shape():
    data = json.loads(format_json([_HIGH]))
    assert data[0]["type"] == "SCOPE_TRAP"
    assert data[0]["items"][0]["label"] == "a"


def test_format_text_has_summary_and_rows():
    out = format_text([_HIGH, _LOW])
    assert "2 findings" in out
    assert "SCOPE_TRAP" in out and "NAME_COLLISION" in out


def test_parser_defaults():
    args = build_parser().parse_args(["scan", "some/dir"])
    assert (args.gate, args.fmt, args.min_danger, args.fail_on) == ("auto", "text", "low", "high")


def test_main_scans_a_semantic_only_env(tmp_path, capsys):
    sem = tmp_path / "semantic"
    sem.mkdir()
    (sem / "semantic_layer.yml").write_text(
        "segments:\n"
        "  - {name: active, filter: 'is_active = true'}\n"
        "metrics:\n"
        "  - {name: value_moments, entity: user, agg: sum, base: agg_active_days, measure: moments}\n"
        "  - {name: real_value_moments, entity: user, agg: sum, base: agg_active_days,"
        " measure: moments, segment: active}\n")

    code = main(["scan", str(tmp_path), "--gate", "lexical", "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert any(f["type"] == "SCOPE_TRAP" for f in payload)
    assert code == 1                              # a high-danger finding -> non-zero exit


def test_format_text_cites_source_location_and_detail():
    from preflight.model import Source
    f = Finding("SCOPE_TRAP", "high", "silently scoped",
                (Item("sl:a", "a", "semantic", Source("layer.yml", 12)),
                 Item("sl:b", "b", "semantic", Source("layer.yml", 20))))
    summary = format_text([f])
    assert "layer.yml:12: [SCOPE_TRAP]" in summary        # anchored to the first source
    detailed = format_text([f], detail=True, read_line=lambda p, n: f"  metric_{n}:")
    assert "layer.yml:12" in detailed and "layer.yml:20" in detailed   # every site listed
    assert "metric_12:" in detailed                        # the injected source line, stripped
