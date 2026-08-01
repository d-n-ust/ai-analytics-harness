"""What a set of citations STATES, written from the governed values rather than by the model.

A measurement is a sentence the evidence already contains. `r2:days_per_user.pct_change` together
with its two levels says "days per user fell 16.44%, from 2.7177 to 2.2709" and says nothing
else, and the harness can write that as well as the model can — better, in the one respect that
matters, because it cannot write anything the citation does not support.

WHY THIS EXISTS

A claim carries free prose plus either evidence or premises, and nothing connects the two. The
audit asks whether the citations resolve and whether a stated figure matches them. It never asks
whether the SENTENCE is one those citations could support, so a conclusion in a measurement's
clothing passes every check:

    "Within active_users, new signups fell 24.84% and activation_rate fell 28.93%, so acquisition
     signals weakened but DID NOT CAUSE the net engagement drop."
        cited: new_signups.pct_change, activation_rate.pct_change

Those two numbers cannot rule acquisition out. What rules it out is that breadth ROSE and its
contribution is negative — a fact in a different claim that this one never points at. Yet the
claim is perfectly bound: real numbers, correctly cited, and the load-bearing assertion of the
whole answer smuggled into the prose beside them.

Detecting that after the fact means classifying English, by keyword or by model, and both are the
kind of check this harness exists to avoid. So it is not detected. When measurements are rendered,
the model never writes their words, a measurement CANNOT contain an argument, and everything the
model does write is by construction an inference that must name its premises.
"""

from __future__ import annotations

__all__ = ["measurement_text", "subject_of"]

# The fields a decomposition exposes per subject, and how they read together.
_LEVELS = ("value_a", "value_b")
_CHANGE = "pct_change"
_SHARE = "contribution_share"


def subject_of(ref: str) -> str:
    """What a reference is ABOUT. `r2:days_per_user.pct_change` -> `days_per_user`; a root field
    like `r2:pct_change` -> "" (the result's own metric, named by the caller)."""
    field = str(ref or "").strip().strip("[]").partition(":")[2]
    return field.rpartition(".")[0] if "." in field else ""


def _fmt(v: float) -> str:
    if v is None:
        return "?"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:,.4f}".rstrip("0").rstrip(".")


def _pct(v: float) -> str:
    return f"{v * 100:+.2f}%" if abs(v) <= 1 else f"{v:+.2f}"


def measurement_text(sources, steps, node_metrics=None) -> str | None:
    """The sentence these citations state, or None when they name nothing resolvable.

    Groups by SUBJECT, because a claim citing `days_per_user`'s two levels and its percent change
    is making one statement about one thing, not three statements. Subjects are joined rather than
    merged: a claim that cites two different children says two things, and the render says both
    instead of choosing."""
    index = {}
    for s in steps or []:
        if s.get("handle") and not s.get("error"):
            labels = [str(x) for x in (s.get("result_labels") or [])]
            values = s.get("result_values") or []
            args = s.get("args") or {}
            index[s["handle"]] = {
                "values": dict(zip(labels, values, strict=False)),
                "all": list(values),
                "metric": args.get("metric") or args.get("node") or s.get("tool") or "",
                "result": str(s.get("result") or ""),
            }

    # subject -> {field: value}, in first-seen order so the sentence follows the citation order
    grouped: dict[str, dict] = {}
    for ref in sources or []:
        text = str(ref).strip().strip("[]")
        handle, _, field = text.partition(":")
        entry = index.get(handle)
        if entry is None:
            return None
        subject = subject_of(text) or entry["metric"]
        if not field:
            # A whole result cited: one number means that number, none means a governed statement.
            if len(entry["all"]) == 1:
                grouped.setdefault(subject, {})["value"] = entry["all"][0]
            else:
                grouped.setdefault(subject, {})["statement"] = entry["result"]
            continue
        value = entry["values"].get(field)
        if value is None and len(entry["all"]) == 1:
            value = entry["all"][0]
        if value is None:
            return None
        grouped.setdefault(subject, {})[field.rpartition(".")[2]] = value

    parts = []
    for subject, fields in grouped.items():
        if "statement" in fields:
            # A governed statement is quoted, not paraphrased: the layer's own words about an edge
            # or a definition are the evidence, and rewording them would be the harness asserting.
            parts.append(f"{subject} reports: {' '.join(fields['statement'].split())[:200]}")
            continue
        a, b = fields.get(_LEVELS[0]), fields.get(_LEVELS[1])
        change = fields.get(_CHANGE)
        share = fields.get(_SHARE)
        if a is not None and b is not None:
            verb = "rose" if b > a else "fell" if b < a else "held at"
            line = (f"{subject} {verb} from {_fmt(a)} to {_fmt(b)}" if verb != "held at"
                    else f"{subject} held at {_fmt(a)}")
            if change is not None:
                line += f" ({_pct(change)})"
        elif change is not None:
            line = f"{subject} changed by {_pct(change)}"
        elif "value" in fields:
            line = f"{subject} was {_fmt(fields['value'])}"
        else:
            line = f"{subject}: " + ", ".join(f"{k} {_fmt(v)}" for k, v in fields.items())
        if share is not None:
            # The share is the whole reason a rise can belong to a fall. Said explicitly, because
            # "+5.98% contributing -0.46" is the sentence a reader misreads when left to infer it.
            direction = ("accounting for" if share > 0 else "pushing the other way by")
            line += f", {direction} {abs(share):.2f} of the change"
        parts.append(line)
    return "; ".join(parts) if parts else None
