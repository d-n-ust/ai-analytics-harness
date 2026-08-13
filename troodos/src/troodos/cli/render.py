"""Terminal presentation.

The layout encodes the product's argument, so it is worth stating rather than leaving implicit.

The number comes first and alone, because that is what was asked for. Everything establishing
*why it should be believed* — the governed metric, the scope it covers, the SQL that ran — sits
beneath it in an aligned evidence block: present, scannable, subordinate. Hiding the SQL would
make the tool unauditable. Leading with it would make it a SQL generator with a chat interface.
Neither is the product.

A refusal renders in the same shape as an answer, not as an error, and in amber rather than red.
It is a result: the agent determined the grounding does not support the question and said so.
Styling it as a failure would teach people to read the most valuable thing this tool does as a
malfunction.

No colour library. ANSI directly, disabled when piped or when NO_COLOR is set, so output stays
greppable and CI logs stay clean.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
import time

# ── glyphs ──────────────────────────────────────────────────────────────────────────────────
# A step marker and a continuation branch. Used for live progress and for the evidence block, so
# the trace the user watched and the receipt they are left with read as one thing.
STEP = "●"
BRANCH = "⎿"


def _supports_colour(stream) -> bool:
    # NO_COLOR is honoured for any non-empty value, per the informal standard.
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return hasattr(stream, "isatty") and stream.isatty()


class _Style:
    """ANSI wrappers that become no-ops when colour is off, so callers never branch on it."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, t):    return self._wrap("1", t)
    def dim(self, t):     return self._wrap("2", t)
    def cyan(self, t):    return self._wrap("36", t)
    def green(self, t):   return self._wrap("32", t)
    def amber(self, t):   return self._wrap("33", t)
    def red(self, t):     return self._wrap("31", t)
    def blue(self, t):    return self._wrap("34", t)


_OUT = _Style(_supports_colour(sys.stdout))
_ERR = _Style(_supports_colour(sys.stderr))


def _width(default: int = 88) -> int:
    try:
        return min(shutil.get_terminal_size().columns, 100)
    except Exception:  # noqa: BLE001 — a missing terminal is not an error worth surfacing
        return default


# ── SQL ─────────────────────────────────────────────────────────────────────────────────────
# The compiled SQL arrives as one long line. Breaking it at clause boundaries is the difference
# between evidence a person will actually read and a wall they will skip.
_CLAUSE = re.compile(
    r"\s+(?=(?:FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|AND|OR)\b)", re.IGNORECASE)
_KEYWORD = re.compile(
    r"\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|AND|OR|AS|DISTINCT|CASE|WHEN|THEN|"
    r"ELSE|END|NOT|IN|IS|NULL|DATE|JOIN|ON|COUNT|SUM|AVG|MIN|MAX)\b", re.IGNORECASE)


def _number(value) -> str:
    """Format a measured value for a human.

    A count that arrives as a float — which it does, because SQL aggregates come back typed by
    the engine rather than by what they mean — must not be shown as `704.0`. A user counting
    people reads a decimal point as a bug in the tool, and they are not entirely wrong.
    Genuine fractions keep their decimals.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"


def format_sql(sql: str, style: _Style) -> list[str]:
    """Break compiled SQL at clause boundaries and tint the keywords."""
    lines: list[str] = []
    for i, part in enumerate(_CLAUSE.split(" ".join(sql.split()))):
        part = part.strip()
        if not part:
            continue
        # Continuation clauses are indented under the clause they qualify, so a long predicate
        # list reads as one thought rather than as several statements.
        indent = "  " if i and re.match(r"^(AND|OR)\b", part, re.IGNORECASE) else ""
        lines.append(indent + _KEYWORD.sub(lambda m: style.blue(m.group(0).upper()), part))
    return lines


# ── live progress ───────────────────────────────────────────────────────────────────────────
class Progress:
    """Live status while the agent works.

    Answering takes several sequential model round trips. Printed nothing, that reads as a hang;
    printed as visible steps, the same wait reads as work. The elapsed clock is always on screen,
    so a slow model is legibly slow rather than ambiguously stuck.

    Everything goes to stderr, so `troodos ask … > out.txt` still captures exactly the answer. On
    a TTY the in-flight line rewrites in place and settles into a permanent one when the step
    finishes; piped, only the settled lines are emitted, because a log full of carriage returns
    is worse than no log.
    """

    _FRIENDLY = {
        "get_schema": "reading the schema",
        "describe_table": "inspecting a table",
        "list_metrics": "listing governed metrics",
        "query_metric": "querying a governed metric",
        "run_sql": "writing SQL",
        "check_coverage": "checking coverage",
        "check_metric_exists": "checking the metric exists",
        "check_segment_defined": "checking the segment",
        "check_causal_evidence": "checking causal evidence",
        "get_metric_tree": "reading the metric tree",
        "explain_change": "decomposing the change",
        "answer": "composing the answer",
        "refuse": "declining",
        "clarify": "asking for clarification",
    }

    @staticmethod
    def _summary(name: str, info: dict) -> str:
        """One glanceable line describing what a tool actually found.

        Each tool gets its own summary because there is no useful generic one. Truncating the raw
        result to N characters — which is what this replaced — yields `evt(eid bigint, uid bigint,
        hid double…)`: technically the output, and unreadable. What a person wants is the shape of
        the answer, not its first 90 bytes.
        """
        content = info.get("content", "")
        args = info.get("args") or {}

        if name == "get_schema":
            # Relations are one per line, each `name(col type, …)`, with `-- comment` lines under.
            rels = [ln for ln in content.splitlines() if ln and not ln.lstrip().startswith("--")]
            documented = content.count("\n  -- ")
            bits = [f"{len(rels)} relation{'s' if len(rels) != 1 else ''}"]
            if documented:
                bits.append(f"{documented} documented")
            return " · ".join(bits)

        if name == "describe_table":
            table = args.get("table") or args.get("name") or ""
            cols = next((ln for ln in content.splitlines() if ln.startswith("columns: ")), "")
            n = len(cols[9:].split(",")) if cols else 0
            return f"{table} · {n} column{'s' if n != 1 else ''}" if n else table

        if name == "list_metrics":
            # Each metric is a multi-line block whose first line starts "- name: description";
            # the rest are indented continuations. Counting every line reports the catalogue as
            # five times its real size.
            n = sum(1 for ln in content.splitlines() if ln.startswith("- "))
            return f"{n} governed metric{'s' if n != 1 else ''}"

        # Neither of the querying tools reports its VALUE here. That value is the answer, and the
        # answer belongs below the rule, once. Printing it during the work and again as the
        # response was the redundancy that made the actual response hard to find.
        if name in ("query_metric", "explain_change"):
            for line in content.splitlines():
                if line.startswith("[scope] "):
                    return line[8:].strip()
            return ""

        if name == "run_sql":
            rows = [ln for ln in content.splitlines()[1:] if ln.strip()]
            if not rows or rows[0] == "(no rows)":
                return "no rows"
            return f"{len(rows)} row{'s' if len(rows) != 1 else ''}"

        # check_* tools answer a yes/no; their first line is already the verdict.
        first = next((ln for ln in content.splitlines() if ln.strip()), "")
        return first[:80]

    def __init__(self, stream=None, enabled: bool = True):
        self._out = stream or sys.stderr
        self._enabled = enabled
        self._s = _ERR if self._out is sys.stderr else _Style(_supports_colour(self._out))
        self._tty = self._enabled and hasattr(self._out, "isatty") and self._out.isatty()
        self._start = time.perf_counter()
        self._pending = 0

    @property
    def _clock(self) -> str:
        return f"{time.perf_counter() - self._start:5.1f}s"

    def _transient(self, text: str) -> None:
        if not (self._enabled and self._tty):
            return
        self._out.write("\r" + text.ljust(self._pending))
        self._pending = len(text)
        self._out.flush()

    def _settle(self, text: str) -> None:
        if not self._enabled:
            return
        if self._tty:
            self._out.write("\r" + text.ljust(self._pending) + "\n")
            self._pending = 0
        else:
            self._out.write(text + "\n")
        self._out.flush()

    def event(self, kind: str, name: str, info: dict) -> None:
        s = self._s
        if kind == "thinking":
            self._transient(f" {s.dim(self._clock)} {s.dim(STEP)} {s.dim('thinking…')}")

        elif kind == "tool":
            self._transient(f" {s.dim(self._clock)} {s.cyan(STEP)} {self._FRIENDLY.get(name, name)}…")

        elif kind == "tool_done":
            label = self._FRIENDLY.get(name, name)
            args = info.get("args") or {}
            # Name what was operated on, so the step says "querying active_users" rather than
            # "querying a governed metric" — the specific noun is the informative part.
            if name == "query_metric" and args.get("metric"):
                label = f"querying {args['metric']}"
            elif name == "describe_table" and (args.get("table") or args.get("name")):
                label = f"inspecting {args.get('table') or args.get('name')}"

            ok = info.get("ok", True)
            self._settle(f" {s.dim(self._clock)} {s.green(STEP) if ok else s.amber(STEP)} {label}")

            # The query — model-authored or compiled from a governed definition — is shown here,
            # once, while it runs. It is the actual claim being made about the data, and this is
            # the only chance to read it before the number arrives wearing its authority.
            # Deliberately NOT repeated beneath the answer: the answer is the answer, and evidence
            # restated after it just makes the response harder to find.
            for line in format_sql(self._query(name, info), s) if self._query(name, info) else []:
                self._settle(f"          {s.dim(line)}")

            summary = self._summary(name, info).strip()
            if summary:
                # Wrapped, not cut. A scope line severed mid-word ("…the whole governed segment; t")
                # is worse than no line: it looks like the tool broke rather than like the line ran
                # out of room. Two lines is the budget — this is a progress trace, not a report.
                wrapped = textwrap.wrap(summary, _width() - 12)[:2]
                self._settle(f"        {s.dim(BRANCH)} {s.dim(wrapped[0] if wrapped else '')}")
                for line in wrapped[1:]:
                    self._settle(f"          {s.dim(line)}")

    @staticmethod
    def _query(name: str, info: dict) -> str:
        """The SQL behind this step, from whichever of the two places it lives in.

        Model-authored SQL is in the call's arguments; a governed metric's compiled SQL is
        appended to the result by the transparency guardrail. Same thing to a reader.
        """
        if name == "run_sql":
            return str((info.get("args") or {}).get("query", "")).strip()
        for line in str(info.get("content", "")).splitlines():
            if line.startswith("[sql] "):
                return line[6:].strip()
        return ""

    def done(self) -> None:
        """Erase any in-flight line so the answer starts on clean ground."""
        if self._enabled and self._tty and self._pending:
            self._out.write("\r" + " " * self._pending + "\r")
            self._out.flush()
            self._pending = 0


# ── the answer ──────────────────────────────────────────────────────────────────────────────
def _evidence(rows: list[tuple[str, object]], style: _Style) -> list[str]:
    """An aligned label/value block. Multi-line values hang under their label rather than
    re-stating it, so the eye tracks one column of labels down the left."""
    if not rows:
        return []
    pad = max(len(label) for label, _ in rows)
    out: list[str] = []
    for label, value in rows:
        lines = value if isinstance(value, list) else str(value).splitlines() or [""]
        head, *rest = lines
        out.append(f"  {style.dim(BRANCH)} {style.dim(label.ljust(pad))}  {head}")
        out += [f"    {' ' * pad}  {line}" for line in rest]
    return out


def render_notice(concessions: tuple[str, ...] | list[str], stream=None) -> str:
    """The guardrails this configuration had to stand down, and why.

    Formatted as a compact block rather than the paragraphs it replaced. The reasons are
    genuinely important — a user believing a guardrail is running when it is not has been misled
    by the tool — but three full sentences at the top of every run is a wall that gets skipped,
    and a warning nobody reads protects nobody. Names first, so the block is scannable; one line
    of reasoning each, indented under.
    """
    s = _ERR if (stream is None or stream is sys.stderr) else _Style(_supports_colour(stream))
    if not concessions:
        return ""

    wrap = _width() - 9
    out = [f"  {s.amber('▲')}  {s.bold('raw SQL mode')} {s.dim('— the model writes queries itself')}"]
    for c in concessions:
        # Each concession reads "<name> is off: <reason>" or "no semantic layer, so <names> …".
        head, _, tail = c.partition(":")
        if tail:
            out.append(f"     {s.amber(head.strip())}")
            body = tail.strip()
        else:
            # The no-semantic-layer case names every stood-down guardrail in one breath. Lift the
            # names onto their own line so the block stays scannable.
            names, _, why = c.partition("cannot act")
            if why:
                listed = names.split("so", 1)[-1].strip().rstrip(",")
                out.append(f"     {s.amber(listed)}")
                body = "cannot act" + why
            else:
                body = c
        out += [f"       {s.dim(line)}" for line in textwrap.wrap(body, wrap) or [""]]
    out.append(f"     {s.dim('reads still enforced — read-only connection, parser-checked')}")
    return "\n".join(out) + "\n"


def _scope_and_sql(answer) -> tuple[str | None, str | None]:
    """Recover the scope line and the SQL that produced the served number.

    Two sources, because there are two paths to a number. A governed call carries the compiled
    SQL in its result, appended by the transparency guardrail; model-authored SQL is only ever in
    the tool call's own arguments. Both end up in the same evidence row, so the receipt looks the
    same either way and the user does not have to know which path ran to find the query.

    Read back off the recorded call rather than recompiled, so what is displayed is provably what
    ran. A recomputation could drift from it and nobody would notice — the exact failure this
    tool exists to make impossible.
    """
    scope = sql = None
    for step in reversed(answer.steps or []):
        if not isinstance(step, dict) or step.get("error"):
            continue
        for line in str(step.get("result", "")).splitlines():
            if line.startswith("[scope] ") and scope is None:
                scope = line[8:].strip()
            elif line.startswith("[sql] ") and sql is None:
                sql = line[6:].strip()
        if sql is None and step.get("tool") == "run_sql":
            sql = str((step.get("args") or {}).get("query", "")).strip() or None
        if sql:
            break
    return scope, sql


def _cost(a) -> str:
    def toks(n: int) -> str:
        return f"{n / 1000:.1f}k" if n >= 1000 else str(n)

    bits = [f"{a.tool_calls} tool call{'s' if a.tool_calls != 1 else ''}",
            f"{a.iterations} iteration{'s' if a.iterations != 1 else ''}"]
    if a.input_tokens or a.output_tokens:
        bits.append(f"{toks(a.input_tokens)} in · {toks(a.output_tokens)} out")
    if getattr(a, "cached_tokens", 0):
        bits.append(f"{toks(a.cached_tokens)} cached")
    return " · ".join(bits)


def render_answer(a, *, show_sql: bool = True, show_steps: bool = False,
                  elapsed: float | None = None) -> str:
    """The response, and only the response.

    Everything the tool DID — the queries, the scope, the tools it reached for — is printed above
    the rule as it happens. Below the rule is what the person asked for: the number, and a
    sentence saying what it counts. Repeating the evidence here made the answer harder to find,
    which is the opposite of what evidence is for.

    Provenance survives as one dim footer line: which governed metric, how much work, how long.
    Enough to know where the number came from; not enough to compete with it. `--steps` restores
    the full trace for anyone debugging.
    """
    s = _OUT
    rule = s.dim("  " + "─" * (_width() - 4))
    out: list[str] = ["", rule, ""]

    if a.outcome == "error":
        out += [f"  {s.red('✗')} {s.bold('Something went wrong')}", "",
                f"    {a.error or 'no detail reported'}", ""]
        return "\n".join(out)

    if a.outcome == "refuse":
        # Amber, not red. The agent worked correctly; the data could not support the question.
        out.append("  " + s.amber("✗") + " " + s.bold("I can't answer that"))
        out += [""] + _para(_refusal_text(a))
    elif a.outcome == "clarify":
        out.append(f"  {s.cyan('?')} {s.bold('One thing first')}")
        out += [""] + _para(str(a.answer or a.explanation or ""))
    else:
        out.append(f"  {s.bold(str(a.answer))}")
        if a.explanation:
            out += [""] + _para(str(a.explanation))

    out += ["", rule, f"  {s.dim(_footer(a, elapsed))}"]

    if show_steps and a.steps:
        out += ["", f"  {s.dim('steps')}"]
        for i, step in enumerate(a.steps, 1):
            name = step.get("tool", "?") if isinstance(step, dict) else str(step)
            ms = step.get("ms", 0) if isinstance(step, dict) else 0
            failed = isinstance(step, dict) and step.get("error")
            mark = s.amber(BRANCH) if failed else s.dim(BRANCH)
            out.append(f"  {mark} {s.dim(f'{i}. {name}')} {s.dim(f'({ms:.0f}ms)')}")

    out.append("")
    return "\n".join(out)


# Said when the model gives a reason code but no `missing` text. Never interpolated into the
# model's own words: `missing` is free text that is sometimes a noun phrase ("net promoter
# score") and sometimes a whole sentence ("NPS is not defined in governed metrics"), and any
# template that fits one mangles the other. The model's sentence is shown as written; the reason
# code is rendered readably in the footer instead, where it cannot collide with prose.
_REFUSAL_FALLBACK: dict[str, str] = {
    "no_governed_definition": "No governed metric defines what was asked.",
    "out_of_coverage": "The period asked for falls outside the data's coverage window.",
    "segment_undefined": "The group asked about is not a governed segment.",
    "no_causal_evidence": "No governed causal evidence links those two things.",
    "wrong_measure": "A metric exists for this, but it measures a different quantity.",
    "wrong_grain": "Not available at the level of detail this question needs.",
    "dimension_not_supported": "That metric cannot be broken down by the dimension named.",
    "ungoverned_dimension_value": "That value is not a governed member of the dimension.",
    "result_empty": "The query ran and came back with nothing.",
}


def _refusal_text(a) -> str:
    missing = str(a.missing or "").strip()
    if missing:
        return missing
    return _REFUSAL_FALLBACK.get(
        a.reason or "", "The grounding available does not support this question.")


def _para(text: str) -> list[str]:
    """Wrap prose to the terminal, indented under the answer."""
    width = _width() - 6
    lines: list[str] = []
    for block in text.strip().splitlines():
        lines += [f"    {ln}" for ln in (textwrap.wrap(block, width) or [""])]
    return lines


def _footer(a, elapsed: float | None) -> str:
    """One line of provenance. Where the number came from, and what it cost to get."""
    bits: list[str] = []
    if a.outcome == "refuse":
        # Reason codes are snake_case machine labels. Spaced out they read as English at no cost
        # to greppability, and this is the one place the code appears now that it is no longer
        # interpolated into the model's prose.
        bits.append((a.reason or "declined").replace("_", " "))
        # Whether the model declined or a guardrail blocked it. Different fixes entirely.
        if a.refused_by:
            bits.append(f"blocked by {a.refused_by}")
    elif a.source_metric:
        bits.append(f"{a.source_metric} · governed")

    bits.append(f"{a.tool_calls} tool call{'s' if a.tool_calls != 1 else ''}")
    if a.input_tokens or a.output_tokens:
        def toks(n: int) -> str:
            return f"{n / 1000:.1f}k" if n >= 1000 else str(n)
        bits.append(f"{toks(a.input_tokens)} in · {toks(a.output_tokens)} out")
    if elapsed is not None:
        bits.append(f"{elapsed:.1f}s")
    return " · ".join(bits)
