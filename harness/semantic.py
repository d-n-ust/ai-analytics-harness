"""The semantic layer (rung 3): a small YAML of governed metrics compiled to SQL.

A metric names one correct definition (the right grain, the right filters, the
right math) so the agent *selects* a metric instead of writing — and possibly
mis-writing — the SQL itself. This is the layer that turns "MRR computed the
model's way" into "MRR computed our way", every time.

The compiler is deliberately small: one base table per metric (the star's marts
are pre-joined, so no join resolution is needed), an aggregate expression, an
optional time column for ranges/grains, and a whitelist of filterable dimensions.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

from .config import NAMED_PERIODS, resolve_period
from .warehouse import run_query

SPEC_PATH = Path(__file__).resolve().parent.parent / "grounding" / "rung3_semantic" / "semantic_layer.yml"


class SemanticError(Exception):
    """Raised for an unknown metric, dimension, or filter — surfaced to the agent."""


def _literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _iso(value, label: str) -> str:
    """Re-parse a date to canonical ISO before it touches SQL. Anything that isn't a
    clean date (including injection payloads) raises rather than reaching the query."""
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise SemanticError(f"{label} date {value!r} is not a valid YYYY-MM-DD.") from exc


# Filler words that don't change which governed object a term refers to.
_STOP = {"the", "our", "a", "an", "of", "per", "rate", "count", "number", "total",
         "average", "avg", "score", "in", "for", "by"}


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t}


def _norm_value(v) -> str:
    """Canonicalise a dimension value for matching: lowercase, and treat spaces,
    underscores, and hyphens alike, so 'paid_search' == 'paid search' == 'Paid-Search'."""
    return re.sub(r"[\s_\-]+", " ", str(v).strip().lower())


def _match_catalog(term: str, names) -> str | None:
    """Return the catalog name a free-text term denotes, or None.

    Strict on purpose: a term matches a name only when it *is* that name plus at
    most filler words (every name token appears in the term, and every term token
    is either a name token or filler). This refuses composites like "MRR growth
    rate" (→ None) that bare-substring matching wrongly accepted, at the cost of
    some true synonyms ("monthly recurring revenue" → None) — a false NO costs
    measurable coverage, a false YES invites fabrication."""
    tt = _tokens(term)
    if not tt:
        return None
    for name in names:
        nt = _tokens(name)
        if nt and nt <= tt and tt <= (nt | _STOP):
            return name
    return None


class SemanticLayer:
    def __init__(self, con, spec_path: Path = SPEC_PATH):
        self.con = con
        self.spec = yaml.safe_load(spec_path.read_text())
        self.metrics: dict[str, dict] = self.spec["metrics"]
        self.governance: dict = self.spec.get("governance", {})

    @property
    def ontology(self) -> dict:
        """The R6 spec-check vocabulary: the entities and segments the
        isolated intent parser may name (each with a short gloss). A superset of the
        metrics — it carries entities like `habits` that have no governed metric — so a
        question can name something we cannot answer. The intent parser sees this, never
        the metric inventory."""
        o = self.governance.get("ontology", {}) or {}
        return {"entities": dict(o.get("entities", {}) or {}),
                "segments": dict(o.get("segments", {}) or {})}

    @property
    def dimensions(self) -> dict:
        """The governed dimensions a metric may be sliced by, with their members — the
        vocabulary the isolated scope intent parser reads to say which slices a question asks for."""
        return dict(self.governance.get("dimensions", {}) or {})

    # -- answerability API: one boolean check per refusal reason ------------ #
    # Each check consults exactly one piece of governance metadata and returns
    # (ok, detail). The same checks serve every caller: the model's check_* tools,
    # the excuse check, and (later) the gate and the rule audit.

    def metric_exists(self, term: str) -> tuple[bool, str]:
        if not _tokens(term):
            return False, "empty term."
        name = _match_catalog(term, self.metrics)
        if name:
            return True, f"governed metric {name!r} matches {term!r}."
        return False, (f"no governed definition matches {term!r}. "
                       f"Catalog: {', '.join(self.metrics)}.")

    def _members(self, dimension: str) -> dict:
        """The governed members of a dimension, {canonical: member}. A member is either a
        synonym list (shorthand) or a dict carrying synonyms plus metadata (availability
        window, member countries)."""
        return self.governance.get("dimensions", {}).get(dimension, {}) or {}

    @staticmethod
    def _synonyms(member) -> list:
        return member.get("synonyms", []) if isinstance(member, dict) else (member or [])

    @staticmethod
    def _meta(member) -> dict:
        return member if isinstance(member, dict) else {}

    def _region_of(self, region, country):
        """A region's launch window also governs its countries — so a country filter
        (PH) is resolved to its region (APAC) before the coverage check, closing the
        dimension that would otherwise bypass the gate. Read from the region dimension."""
        if region:
            return region
        if country:
            c = str(country).upper()
            for name, member in self._members("region").items():
                if c in [str(x).upper() for x in self._meta(member).get("countries", [])]:
                    return name
        return None

    def in_coverage(self, start=None, end=None, region=None, country=None) -> tuple[bool, str]:
        """Is the whole period inside data coverage (and the region's launch window)?
        A period that only partly overlaps coverage is a NO — a partial answer over a
        clipped window is exactly the pre-launch-inclusive trap the check exists to
        catch. A missing end is treated as a point at `start`. A country filter is
        resolved to its region, so PH/ID/IN inherit APAC's launch window."""
        region = self._region_of(region, country)
        cov = self.governance.get("coverage", {})
        d0, d1 = cov.get("data_start"), cov.get("data_end")
        try:
            s = dt.date.fromisoformat(str(start)) if start else None
            e = dt.date.fromisoformat(str(end)) if end else s   # start-only => a point
        except ValueError:
            return False, f"unparseable dates {start!r}..{end!r} (use YYYY-MM-DD)."
        if s is None and e is None:
            return False, "no period given; pass start (and end)."
        lo = s if s is not None else e
        hi = e if e is not None else s
        if d0 and lo < d0:
            return False, (f"period begins {lo}, before data starts {d0}. "
                           f"Restrict the period to on/after {d0}.")
        if d1 and hi > d1:
            return False, f"period ends {hi}, after data ends {d1}."
        if region:
            member = {str(k).lower(): v for k, v in self._members("region").items()}.get(str(region).lower())
            starts = self._meta(member).get("available_from")
            if starts and lo < starts:
                return False, (f"{region} coverage starts {starts}; the period begins {lo}. "
                               "Rows before launch are pre-launch test data — restrict to on/after "
                               f"{starts}.")
        return True, f"period {lo}..{hi} within coverage ({d0}..{d1})."

    def segment_names(self) -> list[str]:
        return list(self.governance.get("segments", {}) or {})

    def test_members(self, dimension: str) -> list:
        """Canonical members of a dimension flagged `test: true` — governed data, so 'is this
        a test channel' is a lookup, not a rule the model has to remember."""
        return [name for name, m in self._members(dimension).items() if self._meta(m).get("test")]

    def _segment_where(self, segment: str) -> str:
        """Compile a governed segment to a WHERE clause. Today's one form is `exclude_test`,
        which drops a dimension's test members; the segment is definitional, not an analyst
        filter, so downstream scope checks treat it as part of the definition."""
        spec = self.governance.get("segments", {}).get(segment)
        if spec is None:
            raise SemanticError(
                f"unknown segment {segment!r}. Governed segments: {', '.join(self.segment_names()) or '(none)'}.")
        dim = spec.get("exclude_test")
        if dim:
            drop = self.test_members(dim)
            return f"{dim} NOT IN ({', '.join(_literal(v) for v in drop)})" if drop else ""
        return ""

    def allowed_filters(self, metric: str) -> set[str] | None:
        """The dimensions a metric may be filtered by — governed metadata, read once from the
        definition. None when the metric is unknown (the caller then has nothing to check)."""
        m = self.metrics.get(metric)
        return self._allowed_filters(m) if m else None

    def resolve_member(self, dimension: str, value):
        """Map a free-text filter value onto the canonical governed member of a dimension,
        via its members + synonyms (case/space/underscore-insensitive) — "iPhone" ->
        platform=ios. Returns the canonical value, or None when the dimension HAS a governed
        vocabulary but nothing matches (an undefined value; the caller refuses rather than
        querying a slice that doesn't exist). A dimension with no governed member list
        passes its value through unchanged (e.g. a boolean flag like is_internal)."""
        members = self._members(dimension)
        if not members:
            return value
        want = _norm_value(value)
        for canonical, member in members.items():
            if want == _norm_value(canonical) or any(want == _norm_value(s) for s in self._synonyms(member)):
                return canonical
        return None

    def segment_defined(self, term: str) -> tuple[bool, str]:
        pops = [str(p) for p in self.governance.get("answerable_terms", [])]
        if not _tokens(term):
            return False, "empty term."
        name = _match_catalog(term, pops)
        if name:
            return True, f"governed segment {name!r} matches {term!r}."
        return False, f"no governed segment matches {term!r}. Defined: {', '.join(pops)}."

    # -- introspection the agent sees -------------------------------------- #
    def list_metrics_text(self) -> str:
        lines = ["Governed metrics (call query_metric with these names):"]
        for name, m in self.metrics.items():
            dims = m.get("dimensions", [])
            bits = [f"- {name}: {m['description']}"]
            syn = m.get("synonyms", [])
            if syn:
                bits.append(f"    also called: {', '.join(syn)}")
            if dims:
                bits.append(f"    group_by / filter dimensions: {', '.join(dims)}")
            if m.get("supports_internal_filter"):
                bits.append("    supports filter is_internal=false")
            if m.get("time_column"):
                bits.append("    time-filterable (period=…) and grainable (time_grain=week|month|day)")
            else:
                bits.append("    point-in-time (as of now); no period filter")
            lines.append("\n".join(bits))
        lines.append(f"\nNamed periods: {', '.join(NAMED_PERIODS)} (or pass explicit start/end 'YYYY-MM-DD').")
        segs = self.governance.get("segments", {}) or {}
        if segs:
            lines.append("\nGoverned segments (pass segment=… to query_metric for a named population):")
            for name, s in segs.items():
                also = f" (also: {', '.join(s.get('synonyms', []))})" if s.get("synonyms") else ""
                lines.append(f"- {name}: {s.get('description', '')}{also}")
        return "\n".join(lines)

    # -- compilation ------------------------------------------------------- #
    def _allowed_filters(self, m: dict) -> set[str]:
        allowed = set(m.get("dimensions", [])) | set(m.get("filterable", []))
        if m.get("supports_internal_filter"):
            allowed.add("is_internal")
        return allowed

    def compile(self, name, group_by=None, filters=None, time_grain=None,
                start=None, end=None, period=None, resolve=True, segment=None) -> str:
        if name not in self.metrics:
            raise SemanticError(
                f"unknown metric {name!r}. Available: {', '.join(self.metrics)}")
        m = self.metrics[name]
        time_col = m.get("time_column")

        select, group = [], []
        if time_grain:
            if not time_col:
                raise SemanticError(f"metric {name!r} has no time dimension to grain by.")
            if time_grain not in ("day", "week", "month"):
                raise SemanticError(f"time_grain {time_grain!r} must be day, week, or month.")
            select.append(f"date_trunc('{time_grain}', {time_col})::date AS period")
            group.append("period")
        for d in group_by or []:
            if d not in m.get("dimensions", []):
                raise SemanticError(
                    f"cannot group {name!r} by {d!r}. Dimensions: {m.get('dimensions', [])}")
            select.append(d)
            group.append(d)
        select.append(f"{m['agg']} AS value")

        where = list(m.get("default_filters", []))
        if segment:
            clause = self._segment_where(segment)   # a governed named filter (e.g. real_acquisition)
            if clause:
                where.append(clause)
        if period is not None:
            try:
                start, end = resolve_period(period)
            except ValueError as exc:
                raise SemanticError(str(exc)) from exc
        if (start or end) and not time_col:
            raise SemanticError(f"metric {name!r} is point-in-time; it takes no period.")
        # Dates are re-parsed to ISO before interpolation — never trust the raw string
        # in SQL (the governed path must not be injectable).
        if start and time_col:
            where.append(f"{time_col} >= DATE '{_iso(start, 'start')}'")
        if end and time_col:
            where.append(f"{time_col} <= DATE '{_iso(end, 'end')}'")

        allowed = self._allowed_filters(m)
        for col, val in (filters or {}).items():
            if col not in allowed:
                raise SemanticError(
                    f"cannot filter {name!r} by {col!r}. Allowed: {sorted(allowed)}")
            # R6: resolve each free-text value to its governed member, or refuse an unknown
            # one. Below the resolve rung (resolve=False) the raw value is used as-is, so an
            # unrecognised or mis-cased value quietly returns an empty slice — the failure
            # the resolver exists to close.
            vals = list(val) if isinstance(val, (list, tuple)) else [val]
            if resolve:
                canon = []
                for v in vals:
                    c = self.resolve_member(col, v)
                    if c is None:
                        known = ", ".join(self.governance.get("dimensions", {}).get(col, {}))
                        raise SemanticError(
                            f"no governed value matches {v!r} for {col!r}. Known {col}: {known}.")
                    canon.append(c)
                vals = canon
            if isinstance(val, (list, tuple)):
                where.append(f"{col} IN ({', '.join(_literal(v) for v in vals)})")
            else:
                where.append(f"{col} = {_literal(vals[0])}")

        sql = f"SELECT {', '.join(select)} FROM {m['base']}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if group:
            sql += " GROUP BY " + ", ".join(group) + " ORDER BY " + ", ".join(group)
        return sql

    def query(self, name, **kw) -> tuple[list[str], list[tuple]]:
        return run_query(self.con, self.compile(name, **kw))

    def query_with_sql(self, name, **kw) -> tuple[str, list[str], list[tuple]]:
        """Like query(), but also returns the compiled SQL, so the caller can show the model
        exactly what was computed (transparency) — not just the number it must trust blindly."""
        sql = self.compile(name, **kw)
        cols, rows = run_query(self.con, sql)
        return sql, cols, rows

    def scope_line(self, name, filters=None, period=None, start=None, end=None,
                   group_by=None, resolve=True) -> str:
        """A one-line, plain statement of what a governed result actually covers — so a filter
        that quietly narrows a 'total' into a subset is visible to the model, not buried in SQL.
        Values are shown resolved (their governed member), or flagged UNKNOWN if unresolvable."""
        m = self.metrics[name]
        when = (f"period={period}" if period
                else f"window {start or '…'}..{end or '…'}" if (start or end) else "all time")
        if filters:
            shown = []
            for col, val in filters.items():
                vals = list(val) if isinstance(val, (list, tuple)) else [val]
                if resolve:
                    vals = [self.resolve_member(col, v) or f"UNKNOWN({v})" for v in vals]
                shown.append(f"{col}={vals}")
            flt = "FILTERED to a subset by " + ", ".join(shown)
        else:
            flt = "no filters — the whole governed segment"
        line = f"covers: {when}; {flt}"
        if m.get("default_filters"):
            line += f"; the metric definition already restricts: {', '.join(m['default_filters'])}"
        if group_by:
            line += f"; broken down by {', '.join(group_by)}"
        return line

    def scalar(self, name, *, filters=None, start=None, end=None, period=None):
        """One number for one metric over one period (used by the metric tree)."""
        _, rows = self.query(name, filters=filters, start=start, end=end, period=period)
        if not rows or rows[0][0] is None:
            return None
        return float(rows[0][0])
