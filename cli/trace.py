"""Render one run as a readable trace — what was asked, what ran, what each guardrail did.

A debug and audit view, not telemetry. It takes a plain row dict and returns text, so nothing
is instrumented and nothing is sent anywhere: everything below was already recorded as a side
effect of how the loop works. The same function renders a run that just happened and a run from
last week's results, which is the point — a trace you can only see live is a trace you cannot
go back to when a number looks wrong.

Layout follows the shape of a run rather than the shape of the data: the configuration first,
then the turns and tool calls interleaved in the order they happened, then the outcome. The
guardrail line uses the same distinction as the ladder — ENFORCED guardrails hold whatever the
model does, ADVISORY ones only work if it cooperates — because that is what a reader needs to
know before believing anything below it.
"""

from __future__ import annotations

import json
import shutil
import sys

from agent.guardrails import GUARDRAILS, Position, parse_cell

# Terminal styling, degraded to nothing when the output is not a terminal.
_C = {"dim": "\033[2m", "bold": "\033[1m", "off": "\033[0m",
      "ok": "\033[32m", "warn": "\033[33m", "bad": "\033[31m", "cyan": "\033[36m"}
_ENFORCED = {Position.ACTION_SPACE, Position.BEFORE, Position.AFTER}


def _paint(colour: bool):
    return (lambda s, c: f"{_C[c]}{s}{_C['off']}") if colour else (lambda s, _c: s)


def _short(value, width: int) -> str:
    """One line of a value, cut to width. Args and results are often long; a trace that wraps
    for twenty lines is not readable, and the full text is in the row."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _guardrail_line(config: str, paint) -> list[str]:
    """Which guardrails this run had on, split by whether they hold regardless of the model."""
    try:
        gset = parse_cell(config)
    except (ValueError, AttributeError):
        return [f"  guardrails  {paint(config or 'unknown', 'dim')}"]
    on = [g for g in GUARDRAILS if getattr(gset, g.name, False)]
    if not on:
        return [f"  guardrails  {paint('none — the bare agent', 'dim')}"]
    enforced = [g.name for g in on if g.position in _ENFORCED]
    advisory = [g.name for g in on if g.position not in _ENFORCED]
    lines = [f"  guardrails  {paint(config, 'bold')}"]
    if enforced:
        lines.append(f"     enforced {paint(' · '.join(enforced), 'cyan')}")
    if advisory:
        lines.append(f"     advisory {paint(' · '.join(advisory), 'dim')}"
                     f" {paint('(works only if the model cooperates)', 'dim')}")
    off = [g.name for g in GUARDRAILS if not getattr(gset, g.name, False)]
    if off:
        lines.append(f"          off {paint(' · '.join(off), 'dim')}")
    return lines


def _steps_and_turns(row: dict, width: int, paint) -> list[str]:
    """Turns and tool calls interleaved in the order they happened.

    A turn's `calls` list says which steps belong to it, so the two recorded sequences can be
    zipped back together without either needing to reference the other."""
    out: list[str] = []
    steps = list(row.get("steps") or [])
    turns = list(row.get("turns") or [])
    cursor = 0
    for i, turn in enumerate(turns, 1):
        ms = turn.get("ms")
        cost = f"{turn.get('in', 0)}+{turn.get('out', 0)} tok"
        cached = turn.get("cached") or 0
        if cached:
            cost += f" ({cached} cached)"
        offered = turn.get("tools_offered", 0)
        timing = f"{ms:>7.0f}ms" if ms is not None else " " * 9
        head = f"  {paint(f'turn {i}', 'bold')}  model  {paint(timing, 'dim')}  "
        head += f"{paint(cost, 'dim')}  {paint(f'{offered} tools offered', 'dim')}"
        if turn.get("closing"):
            head += paint("  ← closing: exit tools only", "warn")
        out.append(head)
        for _name in turn.get("calls") or []:
            if cursor >= len(steps):
                break
            out += _step_lines(steps[cursor], width, paint)
            cursor += 1
        if turn.get("exit"):
            out.append(f"           exit   {paint(turn['exit'], 'bold')}")
    for step in steps[cursor:]:          # older rows carry no turns; show the steps anyway
        out += _step_lines(step, width, paint)
    return out


def _step_lines(step: dict, width: int, paint) -> list[str]:
    blocked_by, reason = step.get("blocked_by"), step.get("blocked_reason")
    failed = step.get("error")
    mark = paint("✗", "bad") if failed else paint("✓", "ok")
    ms = step.get("ms")
    timing = paint(f"{ms:>7.0f}ms" if ms is not None else "        —", "dim")
    lines = [f"      {mark} {paint(step.get('tool', '?'), 'bold'):<24} {timing}  "
             f"{paint(_short(step.get('args'), max(20, width - 58)), 'dim')}"]
    if blocked_by:
        lines.append(f"          {paint('blocked by', 'bad')} {paint(blocked_by, 'bad')}"
                     f" → {paint(reason or '', 'bad')}")
    values = step.get("result_values")
    if values:
        shown = ", ".join(f"{v:g}" for v in values[:6]) + ("…" if len(values) > 6 else "")
        lines.append(f"          {paint('→ ' + shown, 'dim')}")
    elif not blocked_by:
        lines.append(f"          {paint('→ ' + _short(step.get('result'), max(20, width - 14)), 'dim')}")
    return lines


def _outcome_lines(row: dict, paint) -> list[str]:
    outcome = row.get("outcome", "?")
    colour = {"answer": "ok", "refuse": "warn", "clarify": "cyan", "error": "bad"}.get(outcome, "dim")
    lines = [f"  {paint(outcome.upper(), colour)}  {row.get('answer') or row.get('explanation') or ''}"]
    if row.get("declared_value") is not None:
        typed = f"value={row['declared_value']:g}"
        if row.get("source_metric"):
            typed += f"  source_metric={row['source_metric']}"
        if row.get("value_recovered"):
            typed += paint("  (recovered from the answer text, not declared)", "warn")
        lines.append(f"          {paint(typed, 'dim')}")
    if row.get("reason"):
        by = row.get("refused_by")
        lines.append(f"          reason {paint(row['reason'], colour)}"
                     + (f"  {paint('← ' + by, 'cyan')}" if by else ""))
    if row.get("missing"):
        lines.append(f"          missing {paint(_short(row['missing'], 90), 'dim')}")
    verdict = row.get("verifier_verdict")
    if verdict:
        ok = verdict.get("answers_question")
        lines.append(f"  {paint('judge', 'bold')}    "
                     + (paint("passed", "ok") if ok else paint(f"REJECTED · {verdict.get('mismatch')}", "bad")))
        lines.append(f"          {paint(_short(verdict.get('reason'), 96), 'dim')}")
    if row.get("error"):
        lines.append(f"          {paint('error ' + str(row['error']), 'bad')}")
    return lines


def render(row: dict, colour: bool | None = None) -> str:
    """One run as text. `row` is the stored row shape, so this serves live and archived alike.

    Colour defaults to whether stdout is a terminal, so piping the trace to a file or a diff
    gives plain text rather than escape codes."""
    if colour is None:
        colour = sys.stdout.isatty()
    paint = _paint(colour)
    width = min(shutil.get_terminal_size((100, 24)).columns, 110)
    rule = paint("─" * width, "dim")

    head = [rule,
            f"  {paint(_short(row.get('question'), width - 4), 'bold')}",
            f"  {paint('rung ' + str(row.get('rung')), 'dim')} · "
            f"{paint(str(row.get('model')), 'dim')}"
            + (f" · {paint(str(row['main_reasoning']) + ' reasoning', 'dim')}"
               if row.get("main_reasoning") else "")]
    head += _guardrail_line(row.get("config") or "", paint)

    body = _steps_and_turns(row, width, paint)

    # A row written before timing was recorded has no timings — say so rather than print a
    # measured-looking zero. Traces are read when a number looks wrong; the one thing they must
    # never do is invent precision.
    turns, steps = row.get("turns") or [], row.get("steps") or []
    timed = [t.get("ms") for t in turns if t.get("ms") is not None]
    tool_timed = [s.get("ms") for s in steps if s.get("ms") is not None]
    parts = [f"{row.get('tool_calls', 0)} tool calls"]
    if row.get("iterations") is not None:
        parts.append(f"{row['iterations']} iterations")
    parts.append(f"{row.get('input_tokens', 0)}+{row.get('output_tokens', 0)} tokens")
    if timed:
        parts.append(f"model {sum(timed):.0f}ms")
    if tool_timed:
        parts.append(f"tools {sum(tool_timed):.0f}ms")
    if not (timed or tool_timed):
        parts.append("no timings recorded")
    foot = [rule] + _outcome_lines(row, paint) + [f"  {paint(' · '.join(parts), 'dim')}", rule]
    return "\n".join(head + [""] + body + foot)
