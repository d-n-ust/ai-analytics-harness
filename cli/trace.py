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
import textwrap

from agent.guardrails import DECOMPOSE_TOOLS, GOVERNED_TOOLS, GUARDRAILS, Position, parse_cell

from .sqlfmt import format_sql

# Terminal styling, degraded to nothing when the output is not a terminal.
_C = {"dim": "\033[2m", "bold": "\033[1m", "off": "\033[0m",
      "ok": "\033[32m", "warn": "\033[33m", "bad": "\033[31m", "cyan": "\033[36m"}
# REPAIR belongs here: the model has no say in being handed its answer back, so it is enforced in
# the sense this split means — it holds regardless of whether the model cooperates. The line below
# calls the other column "works only if the model cooperates", which a repair plainly does not.
_ENFORCED = {Position.ACTION_SPACE, Position.BEFORE, Position.AFTER, Position.REPAIR}


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
    previous_acts = turns[0].get("acts") if turns else None
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
        # The action space is the same on every turn until something withdraws a tool, so it is
        # stated in the header and repeated here only when it actually changes. A trace that
        # reprints five identical lines per turn buries the one turn where they differ.
        if turn.get("acts") != previous_acts:
            out += _act_lines(turn.get("acts"), paint, "      ")
            previous_acts = turn.get("acts")
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


_MARK = {"refused": ("✗", "bad"), "withdrew": ("−", "cyan"), "narrowed": ("▸", "cyan"),
         "applied": ("+", "cyan"), "allowed": ("✓", "dim"), "stood down": ("·", "dim"),
         # neither served nor refused — the answer went back for another go
         "handed back": ("↺", "warn")}


def _act_lines(acts, paint, indent: str) -> list[str]:
    """Every guardrail that ran, in order, whatever it decided.

    The ones that let a call through matter as much as the one that stopped it: without them a
    trace cannot distinguish "no guardrail ran here" from "every guardrail passed", and those
    are very different claims about a number."""
    lines = []
    for a in acts or []:
        glyph, colour = _MARK.get(a.get("outcome", ""), ("·", "dim"))
        name = a.get("guardrail", "?")
        detail = a.get("detail") or ""
        lines.append(f"{indent}{paint(glyph, colour)} {paint(name, colour)} "
                     f"{paint(a.get('outcome', ''), 'dim')}"
                     + (f" {paint('· ' + _short(detail, 62), 'dim')}" if detail else ""))
    return lines


# Calls whose RESULT is shown in full rather than summarised (arguments are always in full, for
# every tool — see _step_lines). A governed query
# returns a bounded table — the warehouse caps it at MAX_ROWS, the loop at _TRACE_LIMIT — and that
# table, with the [scope] and [sql] the disclosure guardrail appends, is the evidence a served
# number is checked against. Summarising it defeats the reason anyone opens a trace: `→ 976, 1289,
# 2042` says three regions moved and not which is which.
#
# `explain_change` is absent because its result is not a table: it is a JSON document, laid out by
# `_decomposition` instead of printed verbatim. Every other tool stays summarised — `get_schema`
# alone would bury the trace it is meant to make readable.
_SHOWN_IN_FULL = ("query_metric",)

# Where the argument text starts on a step line, so a wrapped argument lines up under itself
# instead of under the tool name: 6 indent + mark + space + 24 name + space + 9 timing + 2.
_ARG_COLUMN = 44


def _purpose_and_args(step: dict) -> tuple[str, dict]:
    """A step's declared purpose, split from the arguments that were actually executed.

    `because` earns its own line rather than sitting inside the argument list: it is a sentence,
    and wrapped inline it would push the metric and the filters — the fields a reader checks a
    number against — down the block. Splitting it also keeps the two readings apart: the
    arguments are what ran, the purpose is what it was for."""
    args = dict(step.get("args") or {})
    return str(args.pop("because", "") or "").strip(), args


def _step_lines(step: dict, width: int, paint) -> list[str]:
    blocked_by, reason = step.get("blocked_by"), step.get("blocked_reason")
    failed = step.get("error")
    mark = paint("✗", "bad") if failed else paint("✓", "ok")
    ms = step.get("ms")
    timing = paint(f"{ms:>7.0f}ms" if ms is not None else "        —", "dim")
    purpose, args = _purpose_and_args(step)
    lines = _act_lines([a for a in (step.get("acts") or []) if a.get("position") == "before"],
                       paint, "        ")
    # ARGUMENTS ARE NEVER CUT, for any tool. They are not a summary of the call — they ARE the
    # call, and they are what a reader checks a number against. A truncated argument list hides
    # exactly the field that decides whether a result answers the question: one run compared
    # `period_a: last_month` against `period_b: prev_week` — a month against a week, which is
    # why it reported a 65% collapse — and the trace cut the line at `{"node": "weekly_value_…`.
    # Results still summarise (see _SHOWN_IN_FULL); a schema dump would bury the trace, an
    # argument list never does.
    shown = textwrap.wrap(json.dumps(args, default=str, sort_keys=True),
                          max(40, width - _ARG_COLUMN)) or [""]
    lines.append(f"      {mark} {paint(step.get('tool', '?'), 'bold'):<24} {timing}  "
                 f"{paint(shown[0], 'dim')}")
    lines += [f"{' ' * _ARG_COLUMN}{paint(line, 'dim')}" for line in shown[1:]]
    if purpose:
        # Wrapped, not truncated. Everything else on a step is evidence ABOUT the call and can be
        # summarised; this is the model's own account of what the call was for, and it is the one
        # thing this rung exists to read. Cutting it would be like cutting the answer — the same
        # reason _outcome_lines wraps rather than shortens.
        body = textwrap.wrap(purpose, max(40, width - 20)) or [""]
        lines.append(f"          {paint('because', 'cyan')} {body[0]}")
        lines += [f"                  {line}" for line in body[1:]]
    if blocked_by:
        lines.append(f"          {paint('blocked by', 'bad')} {paint(blocked_by, 'bad')}"
                     f" → {paint(reason or '', 'bad')}")
    lines += _act_lines([a for a in (step.get("acts") or []) if a.get("position") == "disclosure"],
                        paint, "        ")
    return lines + _result_lines(step, width, paint)


def _decomposition(step: dict, width: int) -> list[str] | None:
    """The metric tree's decomposition as a scannable table, or None if it will not parse.

    `explain_change` returns a sixty-line JSON document. Every number in it is governed — the tree
    computed each one from governed metrics through an identity it declares — so none of it can be
    dropped, but nobody reads a contribution share out of pretty-printed JSON.

    Deliberately NOT shared with `causal_record` in the AFTER guardrails, which renders this same
    dict for the judge. That rendering is a TREATMENT — test_surface pins it — so factoring the two
    together would mean a tweak to this trace silently changed what the judge reads. Two audiences,
    two renderings, and the duplication is the cheaper of the two mistakes.
    """
    handle = step.get("handle") or ""
    text = str(step.get("result") or "")
    prefix = f"[{handle}] "
    if handle and text.startswith(prefix):
        text = text[len(prefix):]
    try:
        out = json.loads(text)
    except ValueError:
        return None
    if not isinstance(out, dict) or "identity_decomposition" not in out:
        return None

    def num(v) -> str:
        return "—" if not isinstance(v, (int, float)) else f"{v:.4g}"

    def pct(v) -> str:
        return "" if not isinstance(v, (int, float)) else f"{v * 100:+.2f}%"

    def row(c: dict, name_w: int) -> str:
        return (f"    {str(c.get('child', '')):<{name_w}}  {num(c.get('value_a')):>7} → "
                f"{num(c.get('value_b')):<7}{pct(c.get('pct_change')):>9}")

    kids = out.get("identity_decomposition") or []
    infl = out.get("influence_candidates") or []
    name_w = max((len(str(c.get("child", ""))) for c in [*kids, *infl]), default=0)
    primary = (out.get("primary_driver") or {}).get("child")

    lines = [f"{prefix if handle else ''}{out.get('node', '?')}  "
             f"{out.get('period_a')} → {out.get('period_b')}:  {num(out.get('value_a'))} → "
             f"{num(out.get('value_b'))}  {pct(out.get('pct_change'))}"]
    if kids:
        lines.append("  identity — exact arithmetic, shares sum to 1")
        for c in kids:
            share = c.get("contribution_share")
            lines.append(row(c, name_w)
                         + (f"   share {share:+.3f}" if isinstance(share, (int, float)) else "")
                         + ("  ← primary" if c.get("child") == primary else ""))
    if infl:
        lines.append("  influence — correlational, never proof of cause")
        for c in infl:
            lines.append(row(c, name_w) + f"   confidence: {c.get('confidence', '?')}")
            # The evidence is the whole point of an influence edge — it is what says whether the
            # edge may be leaned on — so it wraps rather than being cut.
            evidence = " ".join(str(c.get("evidence") or "").split())
            lines += [f"      {line}" for line in textwrap.wrap(evidence, max(40, width - 20))]
    return lines


_SQL_TAG = "[sql] "


def _laid_out(lines: list[str]) -> list[str]:
    """A governed result's lines, with the one carrying SQL expanded for reading.

    Only the display changes: the model was shown, and the row still stores, the single-line query
    the compiler emitted. Continuation lines are indented to the tag's own width so the query
    hangs together as a block under it."""
    out: list[str] = []
    for line in lines:
        if not line.startswith(_SQL_TAG):
            out.append(line)
            continue
        query = format_sql(line[len(_SQL_TAG):])
        out.append(_SQL_TAG + (query[0] if query else ""))
        out += [" " * len(_SQL_TAG) + rest for rest in query[1:]]
    return out


def _result_lines(step: dict, width: int, paint) -> list[str]:
    """What the call returned — in full for a governed query, summarised for everything else.

    A blocked call has no result to show; the block was already reported above, and printing an
    empty arrow under it would read as "returned nothing" rather than "never ran"."""
    if step.get("blocked_by"):
        return []
    text = str(step.get("result") or "")
    body = None
    if step.get("tool") in _SHOWN_IN_FULL:
        body = _laid_out(text.splitlines() or [""])
    elif step.get("tool") in DECOMPOSE_TOOLS:
        body = _decomposition(step, width)       # None when it will not parse — fall through
    if body:
        return ([f"          {paint('→ ' + body[0], 'dim')}"]
                + [f"            {paint(line, 'dim')}" for line in body[1:]])
    values = step.get("result_values")
    if values:                                  # typed numbers read the checks read; the display
        shown = ", ".join(f"{v:g}" for v in values[:6]) + ("…" if len(values) > 6 else "")
        return [f"          {paint('→ ' + shown, 'dim')}"]   # text they came from is in the row
    return [f"          {paint('→ ' + _short(text, max(20, width - 14)), 'dim')}"]


def _claim_lines(row: dict, paint, width: int) -> list:
    """What the answer broke itself into, and what the audit made of each piece.

    The served answer is one assertion among several; without this the trace shows the one
    number that was checked and stays silent about the four that were not."""
    audit = row.get("claim_audit") or {}
    claims = row.get("claims") or []
    if not claims:
        return []
    head = (f"{audit.get('bound', 0)}/{audit.get('n', len(claims))} bound · "
            f"{audit.get('sources', 0)} source(s)")
    for k, label in (("unresolved", "unresolved"), ("mislabelled", "mislabelled"),
                     ("value_mismatch", "value mismatch"), ("unsourced", "unsourced")):
        if audit.get(k):
            head += paint(f" · {audit[k]} {label}", "warn")
    out = [f"  {paint('claims', 'bold')}   {head}"]
    findings = audit.get("findings") or [{} for _ in claims]
    for c, f in zip(claims, findings, strict=False):
        ok = f.get("bound", True) and not f.get("why")
        mark = paint("✓", "ok") if ok else paint("✗", "bad")
        text = " ".join(str(c.get("text") or "").split())
        wrapped = textwrap.wrap(text, max(40, width - 22)) or [""]
        val = c.get("value")
        out.append(f"        {mark} c{(f.get('i', 0)) + 1}  {wrapped[0]}"
                   + (paint(f"  = {val:g}", "dim") if isinstance(val, (int, float))
                      and not isinstance(val, bool) else ""))
        out += [f"             {line}" for line in wrapped[1:]]
        refs = ",".join(str(s) for s in (c.get("sources") or [])) or "—"
        line = paint(f"             ← {refs}", "dim")
        if f.get("why"):
            line += paint(f"   {' · '.join(f['why'])}", "bad")
        out.append(line)
    return out


def _outcome_lines(row: dict, width: int, paint) -> list[str]:
    outcome = row.get("outcome", "?")
    colour = {"answer": "ok", "refuse": "warn", "clarify": "cyan", "error": "bad"}.get(outcome, "dim")
    # The served answer is the one thing in a trace that is never cut. Everything else here is
    # evidence about it and can be summarised; this IS the output, and a trace that hides half
    # of it cannot be used to check the half it shows. Long text wraps instead.
    said = " ".join(str(row.get("answer") or row.get("explanation") or "").split())
    body = textwrap.wrap(said, max(40, width - 10)) or [""]
    lines = [f"  {paint(outcome.upper(), colour)}  {body[0]}"]
    lines += [f"          {line}" for line in body[1:]]
    if row.get("declared_value") is not None:
        typed = f"value={row['declared_value']:g}"
        if row.get("source_metric"):
            typed += f"  source_metric={row['source_metric']}"
        # `sources` is the current field; archived rows carry the singular `source_result`.
        cited = row.get("sources") or ([row["source_result"]] if row.get("source_result") else [])
        typed += (f"  sources={','.join(str(h) for h in cited)}" if cited
                  else paint("  (no sources — a comparison cannot be accounted for)", "warn"))
        if row.get("value_recovered"):
            typed += paint("  (recovered from the answer text, not declared)", "warn")
        lines.append(f"          {paint(typed, 'dim')}")
    if row.get("reason"):
        by = row.get("refused_by")
        lines.append(f"          reason {paint(row['reason'], colour)}"
                     + (f"  {paint('← ' + by, 'cyan')}" if by else ""))
    if row.get("missing"):
        lines.append(f"          missing {paint(_short(row['missing'], 90), 'dim')}")
    lines += _act_lines(row.get("acts"), paint, "        ")
    lines += _claim_lines(row, paint, width)
    verdict = row.get("verifier_verdict")
    if verdict:
        ok = verdict.get("answers_question")
        # The role is WHICH test the judge ran, so a verdict without it cannot be read: the same
        # metric passes as evidence for a claim and fails as the answer to the question.
        role = verdict.get("value_role")
        lines.append(f"  {paint('judge', 'bold')}    "
                     + (paint("passed", "ok") if ok else paint(f"REJECTED · {verdict.get('mismatch')}", "bad"))
                     + (paint(f"  · read the number as {role}", "dim") if role else ""))
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
    opening = (row.get("turns") or [{}])[0].get("acts")
    if opening:
        head.append(f"  {paint('action space', 'dim')}")
        head += _act_lines(opening, paint, "     ")

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
    # How much of the working decomposition the run actually left behind. Reported as a share of
    # the calls that COULD carry a purpose, because that is the only denominator the model had a
    # choice over — counting it against every step would score `get_schema` as a missed
    # declaration. Absent entirely when no governed call ran, rather than printed as 0/0.
    governed = [s for s in steps if s.get("tool") in GOVERNED_TOOLS]
    if governed:
        stated = sum(1 for s in governed if _purpose_and_args(s)[0])
        parts.append(f"purpose stated on {stated}/{len(governed)} governed calls")
    foot = [rule] + _outcome_lines(row, width, paint) + [f"  {paint(' · '.join(parts), 'dim')}", rule]
    return "\n".join(head + [""] + body + foot)
