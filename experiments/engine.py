"""The runner for declarative layer studies. A study is a DIRECTORY, not a script.

    ./bench study                                  the tree: every experiment and its studies
    ./bench study 02_segment --reps 3       bare names resolve if unambiguous
    ./bench study 04_semantic_layer_health/02_segment --mock

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

THE ARM'S LETTER IS A MATRIX COLUMN, NOT AN INDEX, and it means the same thing in every study.
The five columns of 04_semantic_layer_health/primitives_matrix.md, and `COLUMNS` below is the only
place their spelling is fixed:

    A_implicit    the fact is true in the data and stated nowhere
    B_documented  a sentence states it — a comment or a description
    C_modelled    the SHAPE of the warehouse states it
    D_declared    a typed field in the semantic layer states it
    E_enforced    a check refuses when it is violated

So "the C arm" names a kind of repair rather than a position in a list. A letter that has to be
looked up is what went wrong twice: `D_swapped` meant nothing to anyone and became `B_prose_swapped`
mid-run, and three studies later ran three different vocabularies for the same three interventions.
Suffix the letter, never invent a new one — `C_modelled_documented` is a variant OF C, because
documentation is a property any shape can have rather than a rung of its own.

WHAT EACH COLUMN MEANS DIFFERS BY PRIMITIVE, and every study says so in a `columns:` block. The
column QUESTION is fixed; the artifact that answers it is not. Column C for entity is a conformed
star; for segment it is one boolean on a dimension, which every arm already has, so that study
declares the column CONSTANT and ships no arm for it. `_validate_columns` checks the block against
the files on disk, because a block nobody checks drifts exactly as the names did. A study that fills
no cell says `fills_matrix_row: false` instead — `00_catalogue_format` varies rendering, so its
A_prose is not an A_implicit and must never be read as one.

A STUDY'S NUMBER IS ITS ROW IN THE PRIMITIVES MATRIX. `01_entity`, `02_segment`, `05_additivity`
name rows 1, 2 and 5 of 04_semantic_layer_health/primitives_matrix.md, so a folder listing reads as
the framework rather than as a chronology.

    00        reserved for prerequisites that fill no cell. `00_catalogue_format` asks whether the
              way we RENDER a catalogue drives what we measure, which cuts across every row.
    gaps      an unbuilt row. 03 and 04 missing says measure+aggregation and grain are not started.
    __suffix  a variant of the same row: `02_segment__mf` is row 2 on dbt MetricFlow.

An EXPERIMENT's number stays a lab-notebook page — 01 through 04 were assigned as the work began and
mean nothing beyond order.

This overturns the earlier rule, which said a study number was a page number and "deliberately does
NOT encode the framework condition". That was written before the matrix existed, when the S-rules
were the framework and their mapping to studies was not one-to-one. It became actively misleading:
the entity study was numbered 05 and sorted after additivity, which is row 5 — the numbering said
the opposite of the framework. Conditions are still declared inside study.yml as `tests_rules`,
where a list can say more than a number.

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
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agent.grounding import build_grounding
from agent.guardrails import LADDER, parse_cell
from agent.loop import run_agent
from agent.protocol import PARTS as PROTOCOL_PARTS, Protocol
from agent.provenance import Expectation
from agent.models import DEFAULT_MODEL
from agent.providers import get_model, get_verifier
from agent.rungs import capabilities
from evals.gold import compute_gold, load_questions
from evals.grade import grade
from semantic.semantic import SPEC_PATH, SemanticLayer
from warehouse.warehouse import cursor as warehouse_cursor
from warehouse.warehouse import open_warehouse, set_star

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = Path(__file__).resolve().parent
CATALOG = "list_metrics"

# Periods the invariant is checked over. Three rather than one because a filter that changes no
# rows in one week can change plenty in another, and an arm that differs only in July is still an
# arm that differs.
_CHECK_PERIODS = ("last_week", "last_month", "june_2026")


# ---------------------------------------------------------------------------- patching

def _reference_layer(con, base, engine: str):
    """The layer an arm's numbers are compared against, built by whichever engine the study uses."""
    if engine == "metricflow":
        from semantic.metricflow_engine import MetricFlowLayer
        return MetricFlowLayer(con, base)
    return SemanticLayer(con, spec_path=base)


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
    # An arm that IS a layer rather than a delta against one. Needed because MetricFlow parses a
    # DIRECTORY of multi-document YAML, which the patch language cannot express. A patch is still
    # the default and the better form — a forked layer drifts, which study 01 paid for once — so
    # this is opt-in and the arm file still carries claim, level and grading either way.
    layer_dir: str = ""
    # WHICH ENGINE SERVES THIS ARM'S LAYER, when it differs from the study's. A peer of
    # `environment` and `agent`, and per-arm for the same reason they are: a study can hold three
    # arms below any semantic layer and one arm on a governed one, and that one arm's engine is a
    # property of the arm rather than of the study. `00_primitive_load` is the case — A, B and C
    # write SQL and only D has a layer, so `engine: metricflow` at study level would name an engine
    # for three arms that never reach one.
    engine: str = ""
    # A third kind of arm. `patch` varies WHAT the layer declares and `layer_dir` swaps the layer
    # wholesale; this varies only HOW the same layer is written down. It is the one arm kind whose
    # treatment provably changes no facts — which `check_same_facts` enforces.
    catalogue_format: str = ""
    # Optional catalogue fields this arm renders. Lets an arm vary whether a fact REACHES the agent
    # while the layer computing the numbers stays byte-identical — the cleanest treatment available,
    # because no new sentence, synonym or metric can explain a difference.
    catalogue_fields: tuple = ()
    # This arm's own warehouse: `{tables: raw|star, views: {...}, docs: {...}}`. Empty means the
    # shared one. An arm that declares it gets a private schema, which is what lets a study compare
    # WAREHOUSE SHAPES rather than only catalogue content.
    environment: dict = field(default_factory=dict)
    # WHAT THE AGENT IS: model, reasoning effort, guardrail cell, judge. A peer of `environment`,
    # which says what the agent can SEE — together they are the whole of a run's configuration, and
    # neither used to be written down in the arm at all.
    agent: dict = field(default_factory=dict)
    # The grounding rung this arm runs at, when the study compares INTERVENTION LEVELS rather than
    # layer content. Empty means the study's rung. An arm that changes rung changes the agent's tool
    # surface — raw SQL below rung 3, `query_metric` at and above it — so the catalogue guards below
    # do not apply to it and are skipped rather than quietly passing on an absent catalogue.
    rung: float = 0
    # metric -> {metric, segment}: how a case's expected metric is REACHED in this arm. A structural
    # arm may move a segment from a name into an argument; the expectation moves with it, which is a
    # translation of the same demand and not a relaxation of it.
    equivalents: dict = field(default_factory=dict)
    changes_candidate_count: bool = False

    KEYS = {"level", "claim", "patch", "delete", "reorder", "grading",
            "changes_candidate_count", "layer_dir", "engine",
            "catalogue_format", "catalogue_fields",
            "rung", "environment", "agent"}

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
                   reorder=d.get("reorder") or {}, layer_dir=d.get("layer_dir", ""),
                   engine=d.get("engine", ""),
                   catalogue_format=d.get("catalogue_format", ""),
                   catalogue_fields=tuple(d.get("catalogue_fields") or ()),
                   rung=float(d.get("rung") or 0),
                   environment=dict(d.get("environment") or {}),
                   agent=dict(d.get("agent") or {}),
                   equivalents=(d.get("grading") or {}).get("metric_equivalents") or {},
                   changes_candidate_count=bool(d.get("changes_candidate_count")))

    def reach(self, metric: str | None) -> tuple:
        """`(metric, kwargs)` — how a case's gold metric is reached in this arm.

        `kwargs` carries whatever the route needs: `segment` where the layer has named segments,
        `where` where it does not. MetricFlow has no segment construct, so its repair arm reaches
        the same rows through a filter — and an equivalence that could only say "segment" would
        have declared the arm unreachable and hidden the very difference the study is about.
        """
        e = self.equivalents.get(metric)
        if not e:
            return metric, {}
        return e["metric"], {k: v for k, v in e.items() if k != "metric" and v is not None}


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


# THE MATRIX COLUMNS, and the only place their spelling is fixed.
#
# A letter names an intervention from ../04_semantic_layer_health/primitives_matrix.md, and it means
# the same thing in every study — that is what makes two rows comparable at a glance. A variant of a
# column suffixes its letter (`C_modelled_documented`); it never takes a letter of its own, because
# a letter that has to be looked up has stopped being a column.
COLUMNS = {"A": "implicit", "B": "documented", "C": "modelled", "D": "declared", "E": "enforced"}

# A `columns:` value opening with one of these declares that the column has NO arm here, and why.
# Anything else describes the arm that fills it. PARTIAL is deliberately not in this set: it marks
# an arm that exists but is a weaker form of the column than another study's, so it still needs a
# file. MEASURED_ELSEWHERE covers a column that IS filled, but by something other than an arm of
# this study — 05_additivity's enforced cell was measured by moving the whole study between two
# guardrail cells, because the check is a property of the guardrails and not of the layer. See 04_semantic_layer_health/02_segment__mf/study.yml for the case that motivated it.
NO_ARM = ("CONSTANT", "ABSENT", "OPEN", "MEASURED_ELSEWHERE")

# VARIANTS A COLUMN IS EXPECTED TO ACCOUNT FOR. Documentation is a property any shape can have
# rather than a rung of its own, so a study that builds a shape must say whether it also built the
# described version of it — as an arm, or as a status in `columns:`.
#
# ONLY C. `A_implicit` plus documentation is `B_documented`, which is a column in its own right.
# `D_declared` already contains its documentation, because in a semantic layer the description is a
# field. `E_enforced` is a check rather than a shape, so there is nothing to describe.
#
# WHY THE CHECK EXISTS. `00_primitive_load` shipped without `C_modelled_documented` and without a
# word about it, because a variant is not a column and nothing here looked for one. It was found by
# reading a directory listing, which is exactly the failure this module's validation was added to
# prevent. When it was finally built it produced the study's clearest result.
VARIANTS = {"C_modelled": ("C_modelled_documented",)}

# Every key a study.yml may carry. Here rather than inline in `Study.load` because a test used to
# restate the set to assert the loader would accept the file, and a second copy of a rule is a rule
# that can disagree with itself — it did, the first time a key was added.
STUDY_KEYS = frozenset({"title", "base", "engine", "rung", "guardrails", "arms", "tests_rules",
                        "agent", "columns", "fills_matrix_row"})


def _column_letter(arm: str) -> str | None:
    """The matrix column `arm` names, or None if it names none.

    `C_modelled_documented` -> "C". `C_table` -> None: the letter is there but the word is not the
    one C stands for, so the name is this study's own vocabulary rather than a column."""
    letter, _, rest = arm.partition("_")
    base = COLUMNS.get(letter)
    return letter if base and (rest == base or rest.startswith(base + "_")) else None


def _validate_columns(name: str, spec: dict, arms: dict) -> None:
    """Check a study's `columns:` block against the arm files that are actually on disk.

    WHY THIS EXISTS. Three studies used three vocabularies for the same three interventions — the
    letters agreed with the matrix in none of them — and nothing said so until a reader compared two
    folders by hand. The block is the fix, and a block nobody checks drifts exactly as the names did.

    A study either declares `columns:`, or declares `fills_matrix_row: false` and explains itself in
    a comment. Silence is not an option, because silence is indistinguishable from an oversight."""
    cols = spec.get("columns")
    if cols is None:
        if spec.get("fills_matrix_row") is False:
            return
        raise ValueError(
            f"{name}/study.yml: no `columns:` block. Declare what each matrix column means for this "
            f"primitive, or set `fills_matrix_row: false` if this study fills no cell of "
            f"primitives_matrix.md.")

    stray = [c for c in cols if _column_letter(c) is None]
    if stray:
        raise ValueError(
            f"{name}/study.yml: `columns:` key(s) {sorted(stray)} do not name matrix columns. "
            f"A key is a letter plus the word that letter stands for, optionally suffixed — "
            f"{', '.join(f'{k}_{v}' for k, v in COLUMNS.items())}, or e.g. C_modelled_documented.")

    for column, text in cols.items():
        declared_empty = str(text).lstrip().startswith(NO_ARM)
        if declared_empty and column in arms:
            raise ValueError(
                f"{name}/study.yml: column {column} is declared {str(text).split()[0]} — no arm — "
                f"but arms/{column}.yml exists. Delete the file or describe the arm.")
        if not declared_empty and column not in arms:
            raise ValueError(
                f"{name}/study.yml: column {column} is described as if an arm fills it, but "
                f"arms/{column}.yml does not exist. Open the value with one of {NO_ARM} and say why.")

    orphans = [a for a in arms if a not in cols]
    if orphans:
        raise ValueError(
            f"{name}/study.yml: arm file(s) {sorted(orphans)} name no declared column. "
            f"Add them to `columns:`, or rename them to a column they fill.")

    # A variant is not a column, so nothing above notices when one is simply absent. If the base
    # column is built, its variants must be accounted for — built, or declared with a reason.
    for column, variants in VARIANTS.items():
        if column not in arms:
            continue
        for variant in variants:
            if variant in arms or variant in cols:
                continue
            raise ValueError(
                f"{name}/study.yml: arm {column} is built and its variant {variant} is neither "
                f"built nor declared. Documentation is a property any shape can have, so a study "
                f"that models a shape must say whether it also described it. Add arms/{variant}.yml, "
                f"or add a `columns:` entry opening with one of {NO_ARM} and say why not.")


@dataclass
class Study:
    name: str
    title: str
    rung: int
    guardrails: object          # a ladder index, or a cell like "R7-coverage_check"
    base: Path
    arms: dict
    cases: list
    directory: Path
    tests_rules: list = field(default_factory=list)
    engine: str = "harness"
    # The study's agent defaults — model, reasoning, guardrails, judge. An arm may override any of
    # them; see `agent_config`.
    agent: dict = field(default_factory=dict)

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

        Nesting made the honest identifier long — `04_semantic_layer_health/02_segment` — and
        a name nobody will type is a name nobody uses. So the bare `02_segment` resolves too,
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
        unknown = set(spec) - STUDY_KEYS
        if unknown:
            raise ValueError(f"{name}/study.yml: unknown key(s) {sorted(unknown)}")
        arms = {p.stem: Arm.load(p) for p in sorted((d / "arms").glob("*.yml"))}
        order = spec.get("arms") or sorted(arms)
        missing = [a for a in order if a not in arms]
        if missing:
            raise SystemExit(f"{name}: study.yml lists arm(s) with no file: {', '.join(missing)}")
        _validate_columns(name, spec, arms)
        # The SAME validator the frozen set uses, pointed at this directory. Reading cases.yml
        # directly is what let a refuse case carry a free-text `reason` instead of one of
        # REFUSAL_REASONS: the grader compares that field to an enum, so every refusal — including
        # the only discriminating question in the set — would have graded MISS in every arm, after
        # the money was spent, for a reason no output mentions. `study.yml` and `arms/*.yml` declare
        # no `cases`, so they contribute nothing and need no exclusion.
        # A study whose treatment does not touch the layer can use the FROZEN set rather than a
        # purpose-written one, and says so instead of copying it — a copy is a second denominator,
        # free to drift from the first and silently move every published rate.
        marker = yaml.safe_load((d / "cases.yml").read_text()) or {} if (d / "cases.yml").exists() else {}
        cases = load_questions() if marker.get("use_frozen_cases") else load_questions(d)
        # For a metricflow study this is a DIRECTORY of YAML, so it is resolved but not read here.
        base = ROOT / spec["base"] if spec.get("base") else SPEC_PATH
        return cls(name=name, title=spec.get("title", name), rung=spec.get("rung", 3),
                   guardrails=spec.get("guardrails", 7), base=base,
                   arms={a: arms[a] for a in order}, cases=cases, directory=d,
                   tests_rules=spec.get("tests_rules") or [],
                   agent=dict(spec.get("agent") or {}),
                   engine=spec.get("engine", "harness"))

    # -- generation ---------------------------------------------------------- #
    def materialize(self, into: Path) -> dict:
        """Write every arm's full layer. These files are OUTPUT: regenerated each run, never edited,
        and kept with the results so the exact layer a number came from is recoverable."""
        into.mkdir(parents=True, exist_ok=True)
        paths = {}
        # An arm that points at a directory is used AS IT IS — there is nothing to generate, and
        # copying it would create the second copy this engine exists to avoid.
        patched = {n: a for n, a in self.arms.items() if not a.layer_dir}
        for name, arm in self.arms.items():
            if arm.layer_dir:
                d = self.directory / arm.layer_dir
                if not d.is_dir():
                    raise SystemExit(f"{self.name}/arms/{name}.yml: layer_dir {arm.layer_dir!r} "
                                     f"is not a directory under {self.directory}")
                paths[name] = d
        if not patched:
            return paths
        spec = yaml.safe_load(self.base.read_text())
        for name, arm in patched.items():
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
    # Nothing to compare below two catalogues. `--arms X` on a single arm, or a study whose arms sit
    # below the semantic layer, left this comparing an empty set and failing with an empty message —
    # a guard that fires on its own degenerate input teaches nobody anything.
    if len(counts) < 2 or len(set(counts.values())) == 1:
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


def _value(layer, metric: str, period: str, route: dict | None = None):
    """One number from any engine, through the interface both implement.

    `query_with_sql` rather than `query`, because that is what `semantic/engine.py` declares and a
    MetricFlow arm has no other entry point. The measure is the `value` column every engine aliases
    to — the same contract the AFTER guardrails rely on.
    """
    _sql, cols, rows = layer.query_with_sql(metric, period=period, **(route or {}))
    if not rows:
        return None
    idx = cols.index("value") if "value" in cols else len(cols) - 1
    return rows[0][idx]


def _catalogue_id(layer) -> dict:
    """`{sha, chars}` for the catalogue a layer renders — the run's provenance for its own
    treatment surface.

    Stored per arm so a later reader can ask whether two runs saw the same catalogue. Without it,
    results from before and after a renderer change sit in the same directory looking comparable,
    and nothing on disk says they are not.
    """
    import hashlib
    text = layer.list_metrics_text()
    return {"sha": hashlib.sha256(text.encode()).hexdigest()[:12], "chars": len(text)}


def check_same_facts(layers: dict, arms: dict) -> list[str]:
    """Every rendering must CONTAIN the same facts. The stronger sibling of the same-numbers
    invariant, and available only to a study whose arms vary the format.

    Same numbers proves the arms can reach the same answers. Same facts proves they were TOLD the
    same things — which is what "these differ only in arrangement" means, and without it a format
    arm that quietly drops a synonym is measuring content again under a format's name. That is not
    hypothetical: the metricflow renderer silently dropped dimension descriptions and an arm ran
    three times with its treatment absent.
    """
    formats = {n: a.catalogue_format for n, a in arms.items() if a.catalogue_format}
    if len(formats) < 2:
        return []
    from semantic.renderers import FIELDS, content_words, same_facts
    problems = []
    reference = reference_name = None
    rendered = {}
    for name in formats:
        layer = layers.get(name)
        if layer is None:
            continue
        facts, text = same_facts(layer), layer.list_metrics_text()
        rendered[name] = text
        if reference is None:
            reference, reference_name = facts, name
        # The DECLARED pairs must match first. A format that states fewer (metric, field) pairs is
        # not a different arrangement of one catalogue; it is a smaller catalogue.
        for gap in sorted(set(reference) - set(facts)):
            problems.append(f"{name}: states nothing for {gap[0]}.{gap[1]}, which "
                            f"{reference_name} states")
        for pair, expected in reference.items():
            if facts.get(pair) not in (None, expected):
                problems.append(f"{name}: {pair[0]}.{pair[1]} differs from {reference_name}'s")
            missing = sorted(v for v in expected if str(v) and str(v) not in text)
            if missing:
                problems.append(f"{name} ({formats[name]}): {pair[0]}.{pair[1]} is declared but "
                                f"absent from the rendered catalogue, e.g. {missing[:3]}")
    # Nothing may be said in one arm and not another. The pair check above covers facts the
    # catalogue DECLARES; this covers the rest of the text — an instruction, a heading, a governance
    # note — which is how one arm came to advertise the `segment` argument alone and then pass an
    # unasked segment, answering 227 where the truth was 283.
    #
    # Compared as WORD SETS: arrangement legitimately changes order and repetition, so anything
    # order-sensitive reports differences that are exactly what the study is measuring.
    reference_words = content_words(rendered[reference_name]) if rendered else set()
    for name, text in rendered.items():
        if name == reference_name:
            continue
        words = content_words(text)
        if words != reference_words:
            problems.append(
                f"{name} ({formats[name]}): does not use the same words as {reference_name} — "
                f"extra {sorted(words - reference_words)[:4]}, "
                f"missing {sorted(reference_words - words)[:4]}. A format carrying a word the "
                f"others lack is a second treatment however it is laid out.")
        # Word parity cannot see a whole FIELD dropped: metrics share dimension names, so a
        # rendering that omits its `group_by` column still contains every value somewhere. The
        # label is what disappears. Since each renderer iterates a shared field tuple, a single
        # metric's field can no longer go missing on its own — only a column, which this catches.
        for label in FIELDS:
            if label not in text:
                problems.append(f"{name} ({formats[name]}): states no {label!r} for any metric, "
                                f"which is a smaller catalogue rather than a different layout")
    return problems


def check_same_numbers(con, base, layers: dict, arms: dict, engine: str = "harness") -> list[str]:
    """Every arm must return the base's numbers, through its own declared equivalences.

    This is the invariant the whole design rests on: if an arm can reach a number the others
    cannot, the experiment measures capability and the legibility question never arises. It runs
    for a MetricFlow study exactly as for ours — an arm nobody held to it is an arm nobody can
    compare, whatever engine produced it.
    """
    ref = _reference_layer(con, base, engine)
    problems, checked = [], 0
    for name in ref.metrics:
        for period in _CHECK_PERIODS:
            try:
                want = _value(ref, name, period)
            except Exception:
                continue
            if want is None:
                continue
            checked += 1
            for arm_name, sl in layers.items():
                metric, route = arms[arm_name].reach(name)
                if metric not in sl.metrics:
                    problems.append(f"{arm_name}: {name} reaches {metric!r}, which it does not offer")
                    continue
                try:
                    got = _value(sl, metric, period, route)
                except Exception as exc:
                    problems.append(f"{arm_name}: {name}@{period} unreachable ({exc})")
                    continue
                if got != want:
                    problems.append(f"{arm_name}: {name}@{period} = {got} != base {want}")
    # 20 was written for a fifteen-metric layer and is meaningless for a smaller one: a
    # three-metric layer cannot reach it however thoroughly it is checked. The bar is whichever is
    # LOWER — twenty pairs, or two periods for every metric the reference offers.
    floor = min(20, 2 * len(ref.metrics))
    if checked < floor:
        problems.append(f"only {checked} metric/period pairs compared against a floor of {floor} "
                        f"({len(ref.metrics)} metrics) — the invariant is barely tested")
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

def agent_config(study, arm=None, args=None) -> dict:
    """What the agent IS, for this arm: model, reasoning effort, guardrail cell, and judge.

    The third of the three things a run is made of — warehouse, semantic layer, agent — and the
    only one that used to live nowhere. Model and effort came from a CLI flag and an environment
    variable, so the same arm file produced different results depending on how it was invoked, and
    nothing in the folder said which.

    RESOLUTION ORDER, narrowest first: the arm's `agent:` block, then the study's, then the command
    line, then the harness defaults. The command line sits BELOW the declarations on purpose — a
    study that pins its model means it, and `--model` silently overriding a pinned study is how two
    runs of "the same study" stop being comparable.
    """
    from agent.models import DEFAULT_MODEL, DEFAULT_REASONING, DEFAULT_VERIFIER_REASONING

    merged: dict = {}
    for source in (getattr(study, "agent", None) or {}, (arm.agent if arm is not None else {}) or {}):
        for key, value in source.items():
            if key == "judge" and isinstance(value, dict):
                merged["judge"] = {**(merged.get("judge") or {}), **value}
            else:
                merged[key] = value

    # `--override-model` beats a pinned study; `--model` does not. The rule the docstring above
    # protects is that an override must never be SILENT — a study that pins its model means it, and
    # two runs of "the same study" on different models are not comparable. An explicitly named flag
    # is not silent: it says what it is doing, the runner prints it, and the model lands in
    # run.json. This is how a study is deliberately swept across model tiers without editing —
    # and therefore quietly falsifying — the file that says what it ran.
    override = getattr(args, "override_model", None) if args is not None else None
    model = override or merged.get("model") or (args.model if args is not None else None) or DEFAULT_MODEL
    judge = merged.get("judge") or {}

    # THE ANSWER PROTOCOL — what an answer must declare about itself. A peer of the guardrail set,
    # not part of it: the set says what the agent may DO, the protocol says what it must SAY.
    #
    #   purpose    a `because` on every governed call
    #   claims     one declaration per assertion, each naming the value it rests on — the evidence
    #              graph, expressed as a contract on the answer
    #   repair     a citation naming nothing is handed back, bounded and once — the repair loop
    #   rendered   the harness writes the measurement's sentence from the cited values, so an
    #              argument cannot be smuggled into a number's prose
    #   framing    rule | role
    #
    # No study could set any of these before, so every study in this repo has run with all four
    # OFF. That is a defensible default and it was never a decision — it is one now.
    protocol = dict(merged.get("protocol") or {})
    unknown = set(protocol) - set(PROTOCOL_PARTS) - {"framing"}
    if unknown:
        raise ValueError(f"agent.protocol: unknown key(s) {sorted(unknown)}; "
                         f"valid: {sorted(PROTOCOL_PARTS) + ['framing']}")
    return {
        "model": model,
        "reasoning": merged.get("reasoning") or DEFAULT_REASONING,
        "guardrails": merged.get("guardrails", None),
        "judge_model": judge.get("model") or model,
        "judge_reasoning": judge.get("reasoning") or DEFAULT_VERIFIER_REASONING,
        "protocol": protocol,
    }


def _guardrails_of(study, arm=None) -> object:
    """A ladder index, or a subtractive cell — the study's, or an arm's own.

    The ladder is CUMULATIVE, so no level expresses "R7 without the two checks MetricFlow cannot
    serve". `parse_cell` already spoke that language for ablation cells; a study may now use it,
    which is what lets two engines be compared at the one cell they can both run.

    AN ARM MAY SET ITS OWN, and one kind of arm has to. The primitives matrix's `enforced` column is
    a runtime check that refuses when a fact is violated — for some primitives that check needs
    nothing but the answer's provenance, and for others it needs a governed layer to compare
    against, so it is DECLARED plus a check rather than an alternative to it. An arm expressing that
    column differs from its neighbour by exactly one guardrail, and no study-level setting can say
    so.
    
    The cost is that arms at different cells are not all mutually comparable, which a study using
    this must state in its own predictions.
    """
    declared = agent_config(study, arm).get("guardrails")
    g = declared if declared is not None else study.guardrails
    return parse_cell(g) if isinstance(g, str) else LADDER[g]


def _run_arm(con, study: Study, arm: Arm, spec_path: Path, cases, golds, args, reps,
             workers: int = 1) -> dict:
    """One arm, over every (rep, case).

    WHY ARMS STAY SEQUENTIAL WHILE CASES MAY NOT. The star views are database-wide objects: an arm
    at rung 1 needs them DROPPED and an arm at rung 2 needs them CREATED, so two arms at different
    rungs cannot share a warehouse at the same moment. Cases within one arm all see the same state,
    so they parallelise safely.

    Each worker gets its own grounding on its own DuckDB cursor — a cursor is an independent
    connection over the same database, so no two threads share a handle. Tool execution measured
    0.01s per run against 7-8s of model latency, so the win is entirely in overlapping the API
    round-trips and nothing is lost to contention.
    """
    # The agent is built PER ARM, because an arm may declare its own model or effort. One model
    # shared by every arm made "which model answered this row" a property of the invocation rather
    # than of the arm, and two rows from the same file were then not necessarily comparable.
    cfg = agent_config(study, arm, args)
    model = get_model(cfg["model"], mock=args.mock, reasoning=cfg["reasoning"])
    verifier = get_verifier(cfg["judge_model"], mock=args.mock)
    # Rejected at construction if incoherent — `rendered` without `claims` offers no citation to
    # render, so the flag could only ever fire zero times.
    protocol = Protocol(**cfg["protocol"]) if cfg["protocol"] else None

    rung = arm.rung or study.rung
    # An arm may declare its own warehouse. When it does, it gets a private schema holding exactly
    # the objects it may see, and a cursor scoped to it — so "this arm cannot read the clean tables"
    # is enforced by the database rather than by not mentioning them. When it does not, the shared
    # warehouse is used and the star views follow the rung, as before.
    # WHICH governed layer this arm gets, and whether it gets one at all. `environment.semantic`
    # names the YAML file, exactly as `tables` and `docs` name theirs; declaring it null means no
    # layer; omitting the key entirely leaves the decision to the rung, which is how every study
    # written before per-arm environments still behaves.
    layer_wanted = layer_path = None
    if "semantic" in arm.environment:
        declared = arm.environment["semantic"]
        layer_wanted = bool(declared)
        if declared:
            layer_path = (ROOT / declared) if not Path(declared).is_absolute() else Path(declared)
            if not layer_path.exists():
                raise SystemExit(f"{arm.name}: environment.semantic names {declared!r}, "
                                 f"which does not exist")
            if arm.patch or arm.delete:
                raise SystemExit(
                    f"{arm.name}: declares both `environment.semantic` and a patch. A patch is a "
                    f"delta against the study's `base`; naming a layer file replaces it. Use one.")
    if layer_path is None:
        layer_path = spec_path

    env = handle = None
    if arm.environment:
        from warehouse.environment import build as build_environment
        env = build_environment(con, f"arm_{study.name.replace('/', '_')}_{arm.name}",
                                arm.environment)
        env.create(con)
        handle = env.cursor(con)
    else:
        set_star(con, capabilities(rung).star)
    grounding = build_grounding(handle if handle is not None else con,
                                rung, guardrails=_guardrails_of(study, arm),
                                                                protocol=protocol,
                                schema=env.schema if env else None,
                                semantic_layer=layer_wanted, spec_path=layer_path,
                                catalogue_format=arm.catalogue_format or "prose",
                                catalogue_fields=arm.catalogue_fields,
                                engine=arm.engine or study.engine)
    # Derived, not declared: the arm promises the model sees the catalogue this layer renders, and
    # the catalogue itself is the assertion. A hand-written substring list is a second description
    # of the same thing, free to fall out of step with it.
    #
    # An arm below rung 3 has no catalogue, so there is nothing to expect. Recording an empty
    # expectation rather than a vacuous one keeps `context_audit` meaning "the treatment reached the
    # model" everywhere it is populated, instead of silently meaning nothing for some arms.
    expectation = ([Expectation(CATALOG, must_contain=(grounding.semantic.list_metrics_text(),))]
                   if grounding.semantic is not None else [])
    blobs: dict = {}
    out = []
    # One grounding per thread, built on that thread's own cursor. `build_grounding` re-reads the
    # layer, so the copies are equal by construction rather than by being shared.
    local = threading.local()

    def _grounding():
        if not hasattr(local, "g"):
            if threading.current_thread() is threading.main_thread():
                local.g = grounding
            else:
                # A worker's cursor must carry the ARM's search_path. A bare `con.cursor()` starts
                # on the default one, where the arm's own tables are not in scope at all — the
                # thread would be reading a different warehouse from the arm it belongs to.
                cur = env.cursor(con) if env is not None else warehouse_cursor(con)
                local.g = build_grounding(cur, rung, guardrails=_guardrails_of(study, arm),
                                          protocol=protocol,
                                          schema=env.schema if env is not None else None,
                                          semantic_layer=layer_wanted, spec_path=layer_path,
                                          catalogue_format=arm.catalogue_format or "prose",
                                          catalogue_fields=arm.catalogue_fields,
                                          engine=arm.engine or study.engine)
        return local.g

    def _one(unit):
            rep, case = unit
            answer = run_agent(case["question"], _grounding(), model,
                               verifier_model=verifier, record_context=True)
            metric, route = arm.reach(case["expect"].get("metric"))
            segment = route.get("segment")
            graded = {**case, "expect": {**case["expect"], **({"metric": metric} if metric else {})}}
            g = grade(answer, graded, golds.get(case["id"]))
            got_segment = next((s.get("args", {}).get("segment") for s in answer.steps or ()
                                if s.get("tool") == "query_metric"), None)
            if segment is not None and got_segment != segment:
                g = {**g, "correct": False, "wrong_segment": f"{got_segment!r} != {segment!r}"}
            audit = answer.context.audit(expectation) if answer.context else ("no context recorded",)
            row = ({"id": case["id"], "rep": rep, "picked": answer.source_metric,
                        "answer": answer.answer, "declared_value": answer.declared_value,
                        "outcome": answer.outcome, "reason": answer.reason,
                        "explanation": answer.explanation, "steps": answer.steps,
                        "tool_calls": answer.tool_calls, "grade": g, "segment": got_segment,
                        "context_audit": list(audit),
                        "context": answer.context.digest() if answer.context else []})
            print(f"  {arm.name:16s} rep{rep} {case['id']:26s} picked={answer.source_metric or '—':16s}"
                  f" {'ok' if g.get('correct') else 'MISS'}"
                  + (f"  ⚠ CONTEXT: {'; '.join(audit)}" if audit else ""), flush=True)
            return row, (answer.context.blobs if answer.context else {})

    units = [(rep, case) for rep in range(reps) for case in cases]
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            done = list(pool.map(_one, units))
    else:
        done = [_one(u) for u in units]
    # Sorted back into (rep, case) order: threads finish out of order, and a results file whose row
    # order depends on which API call returned first is not comparable with the next run's.
    order = {(rep, case["id"]): i for i, (rep, case) in enumerate(units)}
    done.sort(key=lambda d: order[(d[0]["rep"], d[0]["id"])])
    for row, b in done:
        out.append(row)
        blobs.update(b)
    result = {"fingerprint": grounding.fingerprint(), "rows": out, "blobs": blobs,
              "agent": {**cfg, "sampling": model.sampling}}
    if env is not None:
        # The schema goes with the arm that made it. Left behind, the next arm inherits objects it
        # never declared, and every guard would still pass.
        from warehouse.environment import teardown as drop_environment
        drop_environment(con, env.schema)
    return result


def _summarise(study: Study, results: dict, cases: list, vocab: list) -> None:
    arms = list(results)
    want = {c["id"]: c["expect"].get("metric") for c in cases}

    print("\nfingerprints (must all differ — two the same means the treatment never reached the model):")
    for a in arms:
        print(f"  {a:16s} {results[a]['fingerprint']}")

    # Only arms with a catalogue can be audited; an arm below rung 3 has no text to share wording
    # with. Shown as "—" rather than omitted, so the gap is visible instead of looking like a zero.
    audited = [a for a in arms if any(r["arm"] == a for r in vocab)]
    if audited:
        print("\nvocabulary audit — longest verbatim span each question shares with the catalogue:")
        print(f"  {'question':26s} " + " ".join(f"{a:>16s}" for a in arms))
        for case in cases:
            cells = []
            for a in arms:
                row = next((r for r in vocab if r["id"] == case["id"] and r["arm"] == a), None)
                cells.append(f"{row['tokens']:>14d}" if row else f"{'—':>14s}")
            print(f"  {case['id']:26s} " + " ".join(cells))
        worst = max(vocab, key=lambda r: r["tokens"])
        print(f"  longest anywhere: {worst['tokens']} tokens — {worst['arm']}/{worst['id']}: "
              f"{worst['span']!r}")
        if len(audited) < len(arms):
            print(f"  not audited: {', '.join(a for a in arms if a not in audited)} "
                  f"(no catalogue below rung 3)")
        spread = {a: max(r["tokens"] for r in vocab if r["arm"] == a) for a in audited}
        if max(spread.values()) - min(spread.values()) >= 3:
            print("  ⚠ arms differ by 3+ tokens in shared wording. A win may be vocabulary, "
                  "not structure.")

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

    # `correct` requires a refusal to name the RIGHT code; `right action` only requires that it
    # refused rather than invented a number. Both are printed because they answer different
    # questions and can rank the arms differently: refusing instead of fabricating is reliability,
    # naming the reason correctly is usability, and a single column that mixes them charges an arm
    # for a vocabulary slip at the same rate as for a wrong number. Reason accuracy is the gap.
    print(f"\n{'arm':12s} {'correct':>10s} {'right action':>14s} "
          f"{'silent wrong':>14s} {'wrong metric':>14s} {'audit failed':>14s}")
    for a in arms:
        rs = results[a]["rows"]
        action = sum(1 for r in rs
                     if r["grade"].get("correct")
                     or (r["grade"].get("expected_refuse") and r["outcome"] == "refuse"))
        print(f"{a:16s} {sum(1 for r in rs if r['grade'].get('correct')):>6d}/{len(rs):<3d}"
              f" {action:>10d}/{len(rs):<3d}"
              f" {sum(1 for r in rs if r['grade'].get('confident_wrong')):>14d}"
              f" {sum(1 for r in rs if r['grade'].get('wrong_metric')):>14d}"
              f" {sum(1 for r in rs if r['context_audit']):>14d}")

    # Within-arm disagreement on identical input. THE number that decides whether a between-arm gap
    # can be read at all: a cell that contradicts itself across reps is noise, and if there are more
    # noisy cells than the gap is wide, the gap is not a measurement. Printed every run because it
    # was computed by hand after the fact once, and the run before that was published-adjacent.
    # Read off the rows rather than passed in, so it cannot disagree with the data it describes.
    reps = 1 + max((r.get("rep", 0) for a in arms for r in results[a]["rows"]), default=0)
    if reps > 1:
        wobble = [(a, c["id"]) for a in arms for c in cases
                  if len({r["grade"].get("correct")
                          for r in results[a]["rows"] if r["id"] == c["id"]}) > 1]
        cells = len(arms) * len(cases)
        print(f"\nself-disagreement: {len(wobble)} of {cells} arm-question cells gave different "
              f"verdicts across {reps} identical reps.")
        if wobble:
            print("  a gap narrower than this is noise: "
                  + ", ".join(f"{a}/{q}" for a, q in wobble[:4])
                  + (" …" if len(wobble) > 4 else ""))

    discordant = sum(1 for c in cases
                     if len({tuple(sorted(r["grade"].get("correct", False)
                                          for r in results[a]["rows"] if r["id"] == c["id"]))
                             for a in arms}) > 1)
    print(f"\ndiscriminating questions: {discordant} of {len(cases)}."
          + ("  Six is the floor for p < 0.05 on a paired test; below that no number of reps helps."
             if discordant < 6 else ""))


def _persist(study: Study, results: dict, cases, golds, vocab, layers: dict, args, model, verifier) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    # Mirror the source layout: results/experiments/<experiment>/<stamp>-<study>. A study's name
    # contains a slash now, so gluing the timestamp to the whole thing attached it to the
    # EXPERIMENT and made the study a subdirectory — `20260806-234210-04_semantic_layer_health/
    # 02_segment-mock`. Runs were findable but misnamed, and a `*-mock` glob no longer
    # matched them, so cleanup silently skipped every mock run it was meant to remove.
    experiment, _, study_name = study.name.partition("/")
    kind = f"{study_name}-mock" if args.mock else study_name
    out = ROOT / "results" / "experiments" / experiment / f"{stamp}-{kind}"
    # The exact layers this run used, kept beside its numbers. `.build/` is scratch and is
    # regenerated; this copy is the evidence, and without it a stored result names a treatment
    # nobody can reconstruct.
    study.materialize(out / "layers")
    blobs = {sha: t for a in results for sha, t in results[a]["blobs"].items()}
    (out / "context_blobs.json").write_text(json.dumps(blobs, indent=2))
    (out / "run.json").write_text(json.dumps({
        "experiment": study.name, "title": study.title, "rung": study.rung, "tests_rules": study.tests_rules,
        "guardrails": study.guardrails if isinstance(study.guardrails, str) else f"R{study.guardrails}", "base": str(study.base.relative_to(ROOT)),
        # THE MODEL THAT RAN, not the one the command line asked for. `args.model` loses to a
        # model pinned in study.yml, so storing the flag recorded a name that could be false —
        # invisibly, because the default and the pin were the same string in every study written
        # so far. A stored run that misnames its model cannot be compared with anything.
        # READ OFF THE MODEL OBJECT, not off the command line. `args.model` loses to a model
        # pinned in study.yml and to `--override-model`, so storing the flag recorded a name that
        # could be false — invisibly, because the default and the pin were the same string in every
        # study written so far. A stored run that misnames its model cannot be compared with
        # anything. Same rule the line below already applies to `reasoning`.
        "model": model.spec.name, "mock": args.mock, "reps": args.reps,
        # Reasoning effort is a treatment, not a setting: a row that does not carry it cannot
        # be compared with one run at a different depth. Read back off the model rather than
        # off the request, because a model below the requested floor runs at its own.
        "reasoning": model.reasoning,
        # What governed randomness, as sent. Repeat-to-repeat disagreement within one cell is the
        # thing that decides whether a between-arm gap is measurable at all, so a row that cannot
        # say what the sampling settings were cannot be compared with a row from different ones.
        "sampling": model.sampling,
        "verifier_model": verifier.spec.name, "verifier_reasoning": verifier.reasoning,
        "verifier_sampling": verifier.sampling,
        # `catalogue` is the sha and length of the EXACT text this arm rendered. The fingerprint
        # already moves when the catalogue does, but it hashes the whole grounding, so it cannot
        # answer "was this run's catalogue the same as that one's?" — and that question decides
        # whether two runs may be compared at all. A refactor once changed the shipped catalogue on
        # every metric while older results stayed on disk looking comparable.
        "arms": {a: {"fingerprint": results[a]["fingerprint"], "level": study.arms[a].level,
                     "claim": study.arms[a].claim,
                     "rung": study.arms[a].rung or study.rung,
                     "agent": results[a].get("agent"),
                     **({"metrics": len(layers[a].metrics),
                         "catalogue": _catalogue_id(layers[a])} if a in layers else {})}
                 for a in results},
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
    # Arms whose rung has no semantic layer are excluded from the CATALOGUE guards below. They have
    # no catalogue to check, and a guard that "passes" on an absent catalogue is worse than one that
    # declines to look — it reports agreement it never verified. The same-numbers invariant still
    # covers them, because the warehouse is identical and only the agent's tool surface changes.
    catalogued = [a for a in arms if capabilities(study.arms[a].rung or study.rung).semantic]
    if len(catalogued) < len(arms):
        skipped = [a for a in arms if a not in catalogued]
        print(f"note: {', '.join(skipped)} run below the semantic layer, so the catalogue guards "
              f"(candidate count, same facts) do not apply to them.")

    # AN ARM ON ANOTHER ENGINE IS NOT A VARIANT OF THIS STUDY'S BASE, so the invariants that compare
    # it to that base cannot mean anything. A `patch` arm is a delta of `base:` and must reach the
    # base's numbers through its own equivalences; a `layer_dir` arm on a different engine REPLACES
    # the layer, with its own metric names and its own semantics, and asking whether it offers
    # `moments_per_day` is asking whether one layer is the other.
    #
    # Skipped LOUDLY rather than silently, and only for an engine mismatch — a layer_dir arm on the
    # study's own engine is still held to the base, which is how 02_segment__mf's three arms are
    # checked against each other.
    foreign = [a for a in catalogued if study.arms[a].engine and study.arms[a].engine != study.engine]
    if foreign:
        catalogued = [a for a in catalogued if a not in foreign]
        print(f"note: {', '.join(foreign)} declare their own engine, so they are not variants of "
              f"`base:` and the same-numbers and catalogue guards cannot compare them to it. Their "
              f"layer is validated on its own terms — see the arm file.")

    layers = {}
    for a in catalogued:
        layer = _reference_layer(con, paths[a], study.arms[a].engine or study.engine)
        if study.arms[a].catalogue_format:
            layer.catalogue_format = study.arms[a].catalogue_format
        if study.arms[a].catalogue_fields:
            layer.catalogue_fields = study.arms[a].catalogue_fields
        layers[a] = layer

    guarded_arms = {a: study.arms[a] for a in catalogued}
    check_candidate_count(layers, guarded_arms)
    fact_problems = check_same_facts(layers, guarded_arms)
    if fact_problems:
        raise SystemExit("the arms do not state the same FACTS, so a difference between them is\n"
                         "not about arrangement:\n  " + "\n  ".join(fact_problems))
    problems = check_same_numbers(con, study.base, layers, guarded_arms, study.engine)
    if problems:
        raise SystemExit("the same-numbers invariant fails — the arms differ in CAPABILITY, so any\n"
                         "difference between them is not about legibility:\n  " + "\n  ".join(problems))

    vocab = vocabulary_audit(cases, layers)
    golds = compute_gold(con, cases)
    resolved = agent_config(study, None, args)
    model = get_model(resolved["model"], mock=args.mock, reasoning=resolved["reasoning"])
    # The judge is built even when the rung's guardrails leave it idle: which model would
    # have checked the answer is a property of the run, and a row that cannot name it cannot
    # be compared against one from a rung where the judge did fire.
    verifier = get_verifier(resolved["judge_model"], mock=args.mock)

    cell = study.guardrails if isinstance(study.guardrails, str) else f"R{study.guardrails}"
    # Loud, because an override is only safe when it is impossible to miss: two runs of one study
    # on two models are not comparable, and the header is where a reader notices.
    override = (f" [OVERRIDE: study.yml pins {(study.agent or {}).get('model')}]"
                if getattr(args, "override_model", None) else "")
    print(f"study: {study.name} — {study.title}")
    print(f"rung {study.rung} · guardrails {cell}"
          f" · {resolved['model']}/{model.reasoning}{override}"
          f" · judge {verifier.spec.name}/{verifier.reasoning}"
          + (" (MOCK)" if args.mock else "")
          + f" · {len(cases)} questions x {args.reps} reps x {len(arms)} arms")
    print("gold: " + ", ".join(f"{k}={v:g}" for k, v in golds.items() if v is not None))

    results = {a: _run_arm(con, study, study.arms[a], paths[a], cases, golds, args, args.reps,
                           getattr(args, "concurrency", 1))
               for a in arms}
    # PERSIST FIRST. The summary is a rendering of results that already exist, and it used to run
    # before the write — so a formatting bug in it destroyed sixty completed runs that had already
    # been paid for. Reporting may fail; evidence may not be lost.
    out = _persist(study, results, cases, golds, vocab, layers, args, model, verifier)
    _summarise(study, results, cases, vocab)
    print(f"\nwrote {out}")
    print(f"inspect what the model saw:  ./bench context --run {out.relative_to(ROOT)} --full")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("experiment")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--override-model", default=None,
                    help="run every arm on this model, overriding a model pinned in study.yml. "
                         "Use to sweep a study across model tiers; the override is printed and "
                         "stored in run.json.")
    ap.add_argument("--mock", action="store_true", help="mock model — checks wiring, measures nothing")
    ap.add_argument("--arms", default=None, help="comma-separated subset")
    ap.add_argument("--only", default=None, help="comma-separated question ids")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
