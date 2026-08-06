"""The runner for declarative layer studies. A study is a DIRECTORY, not a script.

    ./bench study                                  the tree: every experiment and its studies
    ./bench study 02_segment_in_agg --reps 3       bare names resolve if unambiguous
    ./bench study 04_semantic_layer_health/02_segment_in_agg --mock

TWO LEVELS, BECAUSE THE WORK HAS TWO LEVELS. An EXPERIMENT is a week that ends in an article; a
STUDY is one runnable comparison inside it. Only experiment 04 has studies — 01 and 02 are sweeps
over code (a rung and a guardrail are capabilities the harness builds, not data) and 03 is an
architecture. Their `experiment.yml` says so in `runs:`, so nobody hunts for a config that was
never written.

    experiments/NN_<experiment>/
        experiment.yml           what the week asked, its article, and where its evidence lives
        NN_<defect>/             a study, if this experiment has any
            study.yml            what varies, against which base, at which rung
            cases.yml            the cases (outside evals/cases/, so no frozen denominator moves)
            arms/<rung>_<name>.yml   one patch per arm — usually under ten lines

WHY ARMS ARE PATCHES. The first probe forked the whole semantic layer once per arm: four files,
1,474 lines, to express about forty lines of treatment. Nobody diffs a 370-line YAML, and one arm
quietly acquired a synonym list that matched the question wording — a confound that survived the
run, the review and the write-up, and which is the reason that study's headline cannot be
attributed. Forked files also drift from the layer they are supposed to be a variant OF, silently,
with every run still green. So an arm declares only its DELTA and the full layer is generated:
generated files cannot drift, and the treatment is legible without a diff.

THE ARM'S LETTER IS A LADDER RUNG, NOT AN INDEX, and it means the same thing in every study:

    A_  the fact is absent — nothing the agent can read states it
    B_  the fact is stated in PROSE, in a description, where only a reader can use it
    C_  the fact is DECLARED — a named segment, machine-readable and selectable

So "the C arm" names a kind of repair rather than a position in a list. A letter that has to be
looked up is what went wrong last time — `D_swapped` meant nothing to anyone and was renamed
`B_prose_swapped` mid-run, because it is a variant OF B. Suffix the letter, never invent a new one.

NUMBERS ARE LAB-NOTEBOOK PAGES at both levels: assigned when the work starts, never reused, never
renumbered, gaps fine. A study's number deliberately does NOT encode the framework condition,
because that mapping is not one-to-one — 02 treats S4 and replicates S1. Conditions are declared
inside study.yml as `tests_rules`, where a list can say so.

STUDIES ARE DISCOVERED, NOT REGISTERED. A directory holding `study.yml` is a study that runs, so
there is no index to keep in step with the filesystem — the failure mode of every index ever
written.

WHAT THE ENGINE DERIVES, so it cannot disagree with the arm it describes:

    the same-numbers invariant   every arm must compile to the same values as the base, through
                                 its own declared equivalences — checked before a token is spent
    the context expectation      the EXACT catalogue this arm renders must appear in what the model
                                 read. Not a hand-written list of substrings that can fall behind
                                 the file: the rendered text itself, compared whole
    the vocabulary audit         longest verbatim span shared between each question and each arm's
                                 catalogue, printed every run. Ten lines, and it is the check that
                                 would have caught the first probe's confound before it was paid for
    the candidate-count guard    arms that offer different numbers of metrics are not comparable
                                 unless one says so out loud — under random choice between two
                                 confusable options, deleting one is worth 50 points before any
                                 treatment exists

The last two are confounds that already cost a result. They are properties the runner checks now,
rather than things a careful reader might catch six weeks later.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agent.grounding import build_grounding
from agent.guardrails import LADDER
from agent.loop import run_agent
from agent.provenance import Expectation
from agent.providers import get_model
from agent.rungs import capabilities
from evals.gold import compute_gold, load_questions
from evals.grade import grade
from semantic.semantic import SPEC_PATH, SemanticLayer
from warehouse.warehouse import open_warehouse, set_star

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = Path(__file__).resolve().parent
CATALOG = "list_metrics"

# Periods the invariant is checked over. Three rather than one because a filter that changes no
# rows in one week can change plenty in another, and an arm that differs only in July is still an
# arm that differs.
_CHECK_PERIODS = ("last_week", "last_month", "june_2026")


# ---------------------------------------------------------------------------- patching

def _walk(node: dict, path: str) -> tuple[dict, str]:
    """The container holding `path`'s final key, and that key.

    Every level ABOVE the last must already exist. A patch may add a key; it may not conjure the
    thing the key hangs off. `metrics.power_user.agg` — one letter short — would otherwise create a
    fifteenth metric named `power_user`, run cleanly, and measure a layer nobody wrote.
    """
    parts = path.split(".")
    for i, part in enumerate(parts[:-1]):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"{path}: {'.'.join(parts[:i + 1])} does not exist in the base layer")
        node = node[part]
    if not isinstance(node, dict):
        raise KeyError(f"{path}: {'.'.join(parts[:-1])} is not a mapping")
    return node, parts[-1]


def apply_patch(spec: dict, patch: dict, delete: list[str], reorder: dict | None = None) -> dict:
    """The base layer with one arm's delta applied: keys removed, keys set, keys reordered.

    `reorder` exists because a patch sets VALUES and a position control changes nothing but ORDER —
    and order is rendered, so the model sees it. Without this an arm that only swaps two metrics is
    inexpressible as a delta, which is why the first probe kept a whole forked 371-line file to say
    "the same layer, with two entries the other way round".
    """
    out = copy.deepcopy(spec)
    for path in delete:
        parent, key = _walk(out, path)
        if key not in parent:
            raise KeyError(f"delete {path}: not present — the arm removes something already absent")
        parent.pop(key)
    for path, value in patch.items():
        parent, key = _walk(out, path)
        parent[key] = value
    for path, first in (reorder or {}).items():
        parent, key = _walk(out, path)
        node = parent.get(key)
        if not isinstance(node, dict):
            raise KeyError(f"reorder {path}: not a mapping")
        # Naming an absent key would silently reorder nothing and produce an arm identical to its
        # base — a position control that controls for nothing, and green all the way through.
        missing = [k for k in first if k not in node]
        if missing:
            raise KeyError(f"reorder {path}: no such key(s) {missing}")
        rest = [k for k in node if k not in set(first)]
        parent[key] = {k: node[k] for k in list(first) + rest}
    return out


# ---------------------------------------------------------------------------- the pieces

@dataclass(frozen=True)
class Arm:
    """One treatment, as a delta against the base layer."""

    name: str
    level: str                       # surface | structural
    claim: str
    patch: dict = field(default_factory=dict)
    delete: list = field(default_factory=list)
    reorder: dict = field(default_factory=dict)
    # metric -> {metric, segment}: how a case's expected metric is REACHED in this arm. A structural
    # arm may move a segment from a name into an argument; the expectation moves with it, which is a
    # translation of the same demand and not a relaxation of it.
    equivalents: dict = field(default_factory=dict)
    changes_candidate_count: bool = False

    KEYS = {"level", "claim", "patch", "delete", "reorder", "grading", "changes_candidate_count"}

    @classmethod
    def load(cls, path: Path) -> Arm:
        d = yaml.safe_load(path.read_text()) or {}
        unknown = set(d) - cls.KEYS
        if unknown:
            raise ValueError(f"{path.name}: unknown key(s) {sorted(unknown)}")
        if d.get("level") not in ("surface", "structural"):
            raise ValueError(f"{path.name}: level must be 'surface' or 'structural', got {d.get('level')!r}")
        return cls(name=path.stem, level=d["level"], claim=d.get("claim", ""),
                   patch=d.get("patch") or {}, delete=d.get("delete") or [],
                   reorder=d.get("reorder") or {},
                   equivalents=(d.get("grading") or {}).get("metric_equivalents") or {},
                   changes_candidate_count=bool(d.get("changes_candidate_count")))

    def reach(self, metric: str | None) -> tuple[str | None, str | None]:
        """(metric, segment) this arm expects for a case whose gold metric is `metric`."""
        e = self.equivalents.get(metric)
        return (e["metric"], e.get("segment")) if e else (metric, None)


@dataclass
class Experiment:
    """A week's work ending in an article — the outer level. Not runnable itself.

    Loaded rather than left as prose so it cannot drift: a typo in a key fails here, and `evidence`
    pointing at a path that no longer exists is caught by `problems()` instead of by a reader six
    months later. The manifest POINTS at artifacts and never holds copies of them — `evals/cases/`
    is the frozen set the runner loads and `results/published/` is cited by shipped articles, so
    moving either into a project folder would break a path or shift a published denominator.
    """

    name: str
    title: str
    question: str
    status: str                        # shipped | in_progress | planned
    runs: str                          # declarative | cli | code — how this project's runs happen
    article: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    directory: Path = None

    KEYS = {"title", "question", "status", "runs", "article", "evidence", "notes"}
    STATUSES = {"shipped", "in_progress", "planned"}
    RUNS = {"declarative", "cli", "code"}

    @classmethod
    def load_all(cls) -> list:
        out = []
        for path in sorted(EXPERIMENTS.glob("*/experiment.yml")):
            d = yaml.safe_load(path.read_text()) or {}
            unknown = set(d) - cls.KEYS
            if unknown:
                raise ValueError(f"{path.parent.name}/experiment.yml: unknown key(s) {sorted(unknown)}")
            for field_name, allowed in (("status", cls.STATUSES), ("runs", cls.RUNS)):
                if d.get(field_name) not in allowed:
                    raise ValueError(f"{path.parent.name}/experiment.yml: {field_name} must be one "
                                     f"of {sorted(allowed)}, got {d.get(field_name)!r}")
            out.append(cls(name=path.parent.name, title=d.get("title", path.parent.name),
                           question=d.get("question", ""), status=d["status"], runs=d["runs"],
                           article=d.get("article") or {}, evidence=d.get("evidence") or [],
                           notes=d.get("notes") or [], directory=path.parent))
        return out

    def studies(self) -> list:
        """This experiment's runnable studies, by full name."""
        return [k for k in Study.discover() if k.startswith(f"{self.name}/")]

    def problems(self) -> list:
        """Pointers that have gone stale. A manifest nobody checks is a manifest that lies."""
        missing = [p for p in list(self.evidence) + list(self.notes)
                   if not (ROOT / p).exists() and not (self.directory / p).exists()]
        out = [f"{self.name}: evidence path does not exist: {p}" for p in missing]
        if self.runs == "declarative" and not self.studies():
            out.append(f"{self.name}: declares declarative runs but holds no study.yml")
        if self.runs != "declarative" and self.studies():
            out.append(f"{self.name}: holds studies but declares runs: {self.runs}")
        if self.status == "shipped" and not self.article.get("slug"):
            out.append(f"{self.name}: marked shipped with no article slug")
        return out


def tree() -> str:
    """The four experiments, their status, and the studies each one can run."""
    mark = {"shipped": "✓", "in_progress": "·", "planned": " "}
    lines, problems = [], []
    for e in Experiment.load_all():
        slug = e.article.get("slug")
        where = f"  → {slug}" if slug else "  → article unwritten"
        lines.append(f"{mark.get(e.status, '?')} {e.name:28s} {e.title}{where}")
        lines.append(f"  {'':28s} {e.question}")
        for s in e.studies():
            lines.append(f"  {'':28s}   {s.split('/', 1)[1]:28s} {Study.load(s).title}")
        if e.runs != "declarative":
            lines.append(f"  {'':28s}   (no runnable studies — runs: {e.runs}; see its manifest)")
        problems += e.problems()
    if problems:
        lines += ["", "⚠ stale manifest pointers:"] + [f"  {p}" for p in problems]
    return "\n".join(lines)


@dataclass
class Study:
    name: str
    title: str
    rung: int
    guardrails: int
    base: Path
    arms: dict
    cases: list
    directory: Path
    tests_rules: list = field(default_factory=list)

    @staticmethod
    def discover() -> dict:
        """Every runnable study: `<experiment>/<study>` -> its directory.

        A study IS a directory holding `study.yml`, so a folder that exists is a study that runs.
        There is no register to keep in step with the filesystem, and therefore no way for the two
        to disagree — the failure mode of every index file ever written."""
        return {str(p.parent.relative_to(EXPERIMENTS)): p.parent
                for p in sorted(EXPERIMENTS.rglob("study.yml"))}

    @staticmethod
    def resolve(name: str) -> Path:
        """A study's directory, from either its full path or its bare name.

        Nesting made the honest identifier long — `04_semantic_layer_health/02_segment_in_agg` — and
        a name nobody will type is a name nobody uses. So the bare `02_segment_in_agg` resolves too,
        as long as it is unambiguous; ambiguity is reported rather than guessed at."""
        studies = Study.discover()
        if name in studies:
            return studies[name]
        hits = [path for key, path in studies.items() if path.name == name]
        if len(hits) == 1:
            return hits[0]
        if hits:
            raise SystemExit(f"{name!r} is ambiguous — name the experiment too:\n  "
                             + "\n  ".join(k for k, p in studies.items() if p.name == name))
        raise SystemExit(f"no study {name!r}\navailable:\n  " + "\n  ".join(studies) if studies
                         else f"no study {name!r}, and none are defined")

    @classmethod
    def load(cls, name: str) -> Study:
        d = Study.resolve(name)
        name = str(d.relative_to(EXPERIMENTS))
        spec = yaml.safe_load((d / "study.yml").read_text())
        # Arms have always rejected unknown keys; study.yml silently ignored them, so a typo in
        # `guardrails` would have run the whole thing at the default rung and reported nothing.
        unknown = set(spec) - {"title", "base", "rung", "guardrails", "arms", "tests_rules"}
        if unknown:
            raise ValueError(f"{name}/study.yml: unknown key(s) {sorted(unknown)}")
        arms = {p.stem: Arm.load(p) for p in sorted((d / "arms").glob("*.yml"))}
        order = spec.get("arms") or sorted(arms)
        missing = [a for a in order if a not in arms]
        if missing:
            raise SystemExit(f"{name}: study.yml lists arm(s) with no file: {', '.join(missing)}")
        # The SAME validator the frozen set uses, pointed at this directory. Reading cases.yml
        # directly is what let a refuse case carry a free-text `reason` instead of one of
        # REFUSAL_REASONS: the grader compares that field to an enum, so every refusal — including
        # the only discriminating question in the set — would have graded MISS in every arm, after
        # the money was spent, for a reason no output mentions. `study.yml` and `arms/*.yml` declare
        # no `cases`, so they contribute nothing and need no exclusion.
        cases = load_questions(d)
        base = ROOT / spec["base"] if spec.get("base") else SPEC_PATH
        return cls(name=name, title=spec.get("title", name), rung=spec.get("rung", 3),
                   guardrails=spec.get("guardrails", 7), base=base,
                   arms={a: arms[a] for a in order}, cases=cases, directory=d,
                   tests_rules=spec.get("tests_rules") or [])

    # -- generation ---------------------------------------------------------- #
    def materialize(self, into: Path) -> dict:
        """Write every arm's full layer. These files are OUTPUT: regenerated each run, never edited,
        and kept with the results so the exact layer a number came from is recoverable."""
        into.mkdir(parents=True, exist_ok=True)
        spec = yaml.safe_load(self.base.read_text())
        paths = {}
        for name, arm in self.arms.items():
            out = into / f"{name}.yml"
            out.write_text(f"# GENERATED from {self.base.name} + arms/{name}.yml — do not edit.\n"
                           f"# {arm.claim}\n"
                           + yaml.safe_dump(apply_patch(spec, arm.patch, arm.delete, arm.reorder),
                                            sort_keys=False))
            paths[name] = out
        return paths


# ---------------------------------------------------------------------------- checks

def check_candidate_count(layers: dict, arms: dict) -> None:
    counts = {a: len(sl.metrics) for a, sl in layers.items()}
    if len(set(counts.values())) == 1:
        return
    declared = [a for a in counts if arms[a].changes_candidate_count]
    if not declared:
        raise SystemExit(
            "arms offer different numbers of metrics and no arm declares it:\n  "
            + "\n  ".join(f"{a}: {n} metrics" for a, n in counts.items())
            + "\n\nThis is not a detail. Under random choice between two confusable options, the arm\n"
              "with one fewer scores 50 points higher before any treatment exists. Either equalise\n"
              "the arms, or set `changes_candidate_count: true` on the arm that shrinks and add a\n"
              "control that shrinks by an UNRELATED metric.")


def check_same_numbers(con, base: Path, layers: dict, arms: dict) -> list[str]:
    """Every arm must return the base's numbers, through its own declared equivalences.

    This is the invariant the whole design rests on: if an arm can reach a number the others
    cannot, the experiment measures capability and the legibility question never arises.
    """
    ref = SemanticLayer(con, spec_path=base)
    problems, checked = [], 0
    for name in ref.metrics:
        for period in _CHECK_PERIODS:
            try:
                want = ref.query(name, period=period)
            except Exception:
                continue
            checked += 1
            for arm_name, sl in layers.items():
                metric, segment = arms[arm_name].reach(name)
                try:
                    got = sl.query(metric, period=period, **({"segment": segment} if segment else {}))
                except Exception as exc:
                    problems.append(f"{arm_name}: {name}@{period} unreachable ({exc})")
                    continue
                if got != want:
                    problems.append(f"{arm_name}: {name}@{period} = {got} != base {want}")
    if checked < 20:
        problems.append(f"only {checked} metric/period pairs compared — the invariant is barely tested")
    return problems


_WORD = re.compile(r"[a-z0-9_]+")


def _longest_shared_span(question: str, catalogue: str) -> tuple[int, str]:
    """Longest run of consecutive words the question shares with the rendered catalogue.

    The first probe's decisive arm shared a nine-word span with a question where its rivals shared
    two, and nobody looked until after the money was spent. Cheap to compute, so compute it always.
    """
    q, c = _WORD.findall(question.lower()), _WORD.findall(catalogue.lower())
    index = {}
    for i, w in enumerate(c):
        index.setdefault(w, []).append(i)
    best, span = 0, ""
    for i in range(len(q)):
        for j in index.get(q[i], ()):
            n = 0
            while i + n < len(q) and j + n < len(c) and q[i + n] == c[j + n]:
                n += 1
            if n > best:
                best, span = n, " ".join(q[i:i + n])
    return best, span


def vocabulary_audit(cases: list, layers: dict) -> list[dict]:
    texts = {a: sl.list_metrics_text() for a, sl in layers.items()}
    rows = []
    for case in cases:
        for arm, text in texts.items():
            n, span = _longest_shared_span(case["question"], text)
            rows.append({"id": case["id"], "arm": arm, "tokens": n, "span": span})
    return rows


# ---------------------------------------------------------------------------- running

def _run_arm(con, study: Study, arm: Arm, spec_path: Path, cases, golds, model, reps) -> dict:
    grounding = build_grounding(con, study.rung, guardrails=LADDER[study.guardrails], spec_path=spec_path)
    # Derived, not declared: the arm promises the model sees the catalogue this layer renders, and
    # the catalogue itself is the assertion. A hand-written substring list is a second description
    # of the same thing, free to fall out of step with it.
    expectation = [Expectation(CATALOG, must_contain=(grounding.semantic.list_metrics_text(),))]
    blobs: dict = {}
    out = []
    for rep in range(reps):
        for case in cases:
            answer = run_agent(case["question"], grounding, model, record_context=True)
            metric, segment = arm.reach(case["expect"].get("metric"))
            graded = {**case, "expect": {**case["expect"], **({"metric": metric} if metric else {})}}
            g = grade(answer, graded, golds.get(case["id"]))
            got_segment = next((s.get("args", {}).get("segment") for s in answer.steps or ()
                                if s.get("tool") == "query_metric"), None)
            if segment is not None and got_segment != segment:
                g = {**g, "correct": False, "wrong_segment": f"{got_segment!r} != {segment!r}"}
            audit = answer.context.audit(expectation) if answer.context else ("no context recorded",)
            out.append({"id": case["id"], "rep": rep, "picked": answer.source_metric,
                        "answer": answer.answer, "declared_value": answer.declared_value,
                        "outcome": answer.outcome, "reason": answer.reason,
                        "explanation": answer.explanation, "steps": answer.steps,
                        "tool_calls": answer.tool_calls, "grade": g, "segment": got_segment,
                        "context_audit": list(audit),
                        "context": answer.context.digest() if answer.context else []})
            if answer.context:
                blobs.update(answer.context.blobs)
            print(f"  {arm.name:16s} rep{rep} {case['id']:26s} picked={answer.source_metric or '—':16s}"
                  f" {'ok' if g.get('correct') else 'MISS'}"
                  + (f"  ⚠ CONTEXT: {'; '.join(audit)}" if audit else ""), flush=True)
    return {"fingerprint": grounding.fingerprint(), "rows": out, "blobs": blobs}


def _summarise(study: Study, results: dict, cases: list, vocab: list) -> None:
    arms = list(results)
    want = {c["id"]: c["expect"].get("metric") for c in cases}

    print("\nfingerprints (must all differ — two the same means the treatment never reached the model):")
    for a in arms:
        print(f"  {a:16s} {results[a]['fingerprint']}")

    print("\nvocabulary audit — longest verbatim span each question shares with the catalogue:")
    print(f"  {'question':26s} " + " ".join(f"{a:>16s}" for a in arms))
    for case in cases:
        cells = []
        for a in arms:
            row = next(r for r in vocab if r["id"] == case["id"] and r["arm"] == a)
            cells.append(f"{row['tokens']:>14d}")
        print(f"  {case['id']:26s} " + " ".join(cells))
    worst = max(vocab, key=lambda r: r["tokens"])
    print(f"  longest anywhere: {worst['tokens']} tokens — {worst['arm']}/{worst['id']}: {worst['span']!r}")
    spread = {a: max(r["tokens"] for r in vocab if r["arm"] == a) for a in arms}
    if max(spread.values()) - min(spread.values()) >= 3:
        print("  ⚠ arms differ by 3+ tokens in shared wording. A win may be vocabulary, not structure.")

    print(f"\n{'question':26s} {'wanted':18s} " + " ".join(f"{a:^22s}" for a in arms))
    print("-" * (46 + 23 * len(arms)))
    for case in cases:
        cells = []
        for a in arms:
            rs = [r for r in results[a]["rows"] if r["id"] == case["id"]]
            right = sum(1 for r in rs if r["grade"].get("correct"))
            picks = {r["picked"] or "—" for r in rs}
            pick = next(iter(picks)) if len(picks) == 1 else f"{len(picks)} different"
            segs = {r["segment"] for r in rs if r["segment"]}
            seg = f"/{next(iter(segs))}" if len(segs) == 1 else ""
            cells.append(f"{right}/{len(rs)} {(pick or '—')[:10]:10s}{seg[:8]:8s}")
        print(f"{case['id']:26s} {str(want[case['id']]):18s} " + " ".join(f"{c:^22s}" for c in cells))

    # Refusal cases may accept more than one code. Whenever they do, the codes actually produced
    # have to be visible: a widened list is only defensible if a reader can see what it let through,
    # and "refused for the right reason" and "refused for any reason" are different findings.
    traps = [c for c in cases if c["expect"]["type"] in ("refuse", "ambiguous")]
    if traps:
        print("\nrefusal codes actually produced (accepted: the case's `reason` list):")
        for case in traps:
            accepted = case["expect"]["reason"]
            print(f"  {case['id']:26s} accepts {accepted if isinstance(accepted, list) else [accepted]}")
            for a in arms:
                tally: dict = {}
                for r in (r for r in results[a]["rows"] if r["id"] == case["id"]):
                    key = r["reason"] if r["outcome"] == "refuse" else f"<{r['outcome']}>"
                    tally[key or "<none>"] = tally.get(key or "<none>", 0) + 1
                print(f"    {a:16s} " + ", ".join(f"{k} x{v}" for k, v in sorted(tally.items())))

    print(f"\n{'arm':12s} {'correct':>10s} {'silent wrong':>14s} {'audit failed':>14s}")
    for a in arms:
        rs = results[a]["rows"]
        print(f"{a:16s} {sum(1 for r in rs if r['grade'].get('correct')):>6d}/{len(rs):<3d}"
              f" {sum(1 for r in rs if r['grade'].get('confident_wrong')):>14d}"
              f" {sum(1 for r in rs if r['context_audit']):>14d}")

    discordant = sum(1 for c in cases
                     if len({tuple(sorted(r["grade"].get("correct", False)
                                          for r in results[a]["rows"] if r["id"] == c["id"]))
                             for a in arms}) > 1)
    print(f"\ndiscriminating questions: {discordant} of {len(cases)}."
          + ("  Six is the floor for p < 0.05 on a paired test; below that no number of reps helps."
             if discordant < 6 else ""))


def _persist(study: Study, results: dict, cases, golds, vocab, layers: dict, args) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    kind = f"{study.name}-mock" if args.mock else study.name
    out = ROOT / "results" / "experiments" / f"{stamp}-{kind}"
    # The exact layers this run used, kept beside its numbers. `.build/` is scratch and is
    # regenerated; this copy is the evidence, and without it a stored result names a treatment
    # nobody can reconstruct.
    study.materialize(out / "layers")
    blobs = {sha: t for a in results for sha, t in results[a]["blobs"].items()}
    (out / "context_blobs.json").write_text(json.dumps(blobs, indent=2))
    (out / "run.json").write_text(json.dumps({
        "experiment": study.name, "title": study.title, "rung": study.rung, "tests_rules": study.tests_rules,
        "guardrails": f"R{study.guardrails}", "base": str(study.base.relative_to(ROOT)),
        "model": args.model, "mock": args.mock, "reps": args.reps,
        "arms": {a: {"fingerprint": results[a]["fingerprint"], "level": study.arms[a].level,
                     "claim": study.arms[a].claim, "metrics": len(layers[a].metrics)} for a in results},
        "vocabulary_audit": vocab, "gold": golds, "cases": cases,
        "rows": [dict(arm=a, **r) for a in results for r in results[a]["rows"]],
    }, indent=2, default=str))
    return out


def run(args) -> Path:
    study = Study.load(args.study)
    arms = [a.strip() for a in args.arms.split(",")] if args.arms else list(study.arms)
    unknown = [a for a in arms if a not in study.arms]
    if unknown:
        raise SystemExit(f"unknown arm(s): {', '.join(unknown)}\navailable: {', '.join(study.arms)}")

    cases = study.cases
    if args.only:
        keep = {q.strip() for q in args.only.split(",")}
        unknown = keep - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"unknown question id(s): {', '.join(sorted(unknown))}\n"
                             f"available: {', '.join(c['id'] for c in cases)}")
        cases = [c for c in cases if c["id"] in keep]

    con = open_warehouse(create_star_views=True)
    set_star(con, capabilities(study.rung).star)

    # Generated into the run directory later; built here first because every check below reads them,
    # and a layer that fails a check must cost nothing.
    build = ROOT / ".build" / study.name
    paths = study.materialize(build)
    layers = {a: SemanticLayer(con, spec_path=paths[a]) for a in arms}

    check_candidate_count(layers, study.arms)
    problems = check_same_numbers(con, study.base, layers, study.arms)
    if problems:
        raise SystemExit("the same-numbers invariant fails — the arms differ in CAPABILITY, so any\n"
                         "difference between them is not about legibility:\n  " + "\n  ".join(problems))

    vocab = vocabulary_audit(cases, layers)
    golds = compute_gold(con, cases)
    model = get_model(args.model, mock=args.mock)

    print(f"study: {study.name} — {study.title}")
    print(f"rung {study.rung} · guardrails R{study.guardrails} · model {args.model}"
          + (" (MOCK)" if args.mock else "")
          + f" · {len(cases)} questions x {args.reps} reps x {len(arms)} arms")
    print("gold: " + ", ".join(f"{k}={v:g}" for k, v in golds.items() if v is not None))

    results = {a: _run_arm(con, study, study.arms[a], paths[a], cases, golds, model, args.reps) for a in arms}
    _summarise(study, results, cases, vocab)
    out = _persist(study, results, cases, golds, vocab, layers, args)
    print(f"\nwrote {out}")
    print(f"inspect what the model saw:  ./bench context --run {out.relative_to(ROOT)} --full")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("experiment")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default="gpt-5.6-terra")
    ap.add_argument("--mock", action="store_true", help="mock model — checks wiring, measures nothing")
    ap.add_argument("--arms", default=None, help="comma-separated subset")
    ap.add_argument("--only", default=None, help="comma-separated question ids")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
