"""Adversarial proof of the structural guardrails — NO LLM.

A prompt-based guardrail (rrung 1-3) can only be sampled: run the model N times,
count. A structural guardrail (rrung 4-5: the coverage check and the tool restriction) is a property of
the *system*, so it can be proven by exhaustion. This file is a deterministic
"worst-case agent": it tries every fabrication path we can think of and asserts the
guardrails block all of them. If a technique is truly structural, an omniscient,
maximally-adversarial caller still cannot get a bad number out.

Run: uv run python -m pytest harness/tests/test_structural.py -q     (or run this file directly)
"""

from __future__ import annotations

import harness_paths
from agent.guardrails import LADDER
from agent.runtime.grounding import build_grounding
from semantic.semantic import SemanticError, SemanticLayer
from semantic.tree import MetricTree
from warehouse.warehouse import open_warehouse

# Terms that must never resolve to a governed object — the six impossible questions'
# subjects, plus spelling/garbage/injection variants an adversary would try.
UNGOVERNED_METRICS = [
    "engagement_score", "engagement score", "Engagement Score", "churn risk score",
    "churn_risk", "churn risk", "mrr growth rate", "active user count", "retention score",
    "nps", "", "  ", "value_moments; DROP TABLE u", "engagement_score' OR '1'='1",
]
UNGOVERNED_SEGMENTS = ["enterprise users", "enterprise", "smb", "vip customers", "", "us"]
# (scope, start, end) that fall outside coverage and must be blocked, where `scope` is merged
# into the call. One scope can be named several ways, and a guardrail that reads only one of them
# is not structural: the synonym and group_by rows below were all SERVED until the coverage
# check moved onto the layer's resolved scope. tests/test_gate_properties.py generalises this
# list into a property — a hand-written enumeration only ever proves what someone thought of.
OUT_OF_COVERAGE = [
    ({"filters": {"region": "APAC"}}, "2026-03-01", "2026-03-31"),   # before launch (2026-05-01)
    ({"filters": {"region": "APAC"}}, "2026-04-01", "2026-06-30"),   # straddles launch
    ({"filters": {"region": "asia pacific"}}, "2026-03-01", "2026-03-31"),  # by synonym
    ({"filters": {"region": "Asia Pacific"}}, "2026-04-01", "2026-06-30"),  # by synonym, straddle
    ({"filters": {"country": "PH"}}, "2026-03-01", "2026-03-31"),    # APAC by country
    ({"filters": {"country": "ID"}}, "2026-04-01", "2026-06-30"),    # APAC by country, straddle
    ({"filters": {"country": "IN"}}, "2026-03-15", "2026-03-20"),
    ({"filters": {"country": "philippines"}}, "2026-03-01", "2026-03-31"),  # country by synonym
    ({"group_by": ["region"]}, "2026-03-01", "2026-03-31"),          # the same number, as a row
    ({"group_by": ["country"]}, "2026-04-01", "2026-06-30"),         # ditto, by country
    ({"group_by": ["region"]}, None, None),                          # all time spans pre-launch
    ({}, "2025-07-01", "2025-07-31"),                                # before data starts
    ({}, "2024-01-01", "2024-12-31"),                                # long before data
]


def _check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def prove():
    con = open_warehouse(create_star_views=True)
    sl = SemanticLayer(con)
    MetricTree(sl)          # smoke: the metric tree builds cleanly over the semantic layer
    passed = 0

    # 1. Constrained metric names — no ungoverned term ever resolves to a metric.
    for term in UNGOVERNED_METRICS:
        ok, _ = sl.metric_exists(term)
        _check(not ok, f"metric_exists wrongly accepted {term!r}")
        passed += 1
    for term in UNGOVERNED_SEGMENTS:
        ok, _ = sl.segment_defined(term)
        _check(not ok, f"segment_defined wrongly accepted {term!r}")
        passed += 1

    # 2. The governed path is not injectable — a crafted date raises, never queries.
    for bad in ["2026-06-01' OR '1'='1", "2026-06-01; DROP TABLE u", "not-a-date"]:
        try:
            sl.query("value_moments", start=bad, end="2026-06-30")
            raise AssertionError(f"injection not blocked: {bad!r}")
        except SemanticError:
            passed += 1

    # 3. The interception GATE (rrung 3) blocks every out-of-coverage governed call,
    #    even when the metric itself is real. This is the worst-case agent trying to
    #    pull legitimate metrics over illegitimate periods.
    gate_tb = build_grounding(con, rung=6, guardrails=LADDER[3]).toolbox
    for scope, start, end in OUT_OF_COVERAGE:
        args = {"metric": "value_moments", **scope}
        if start:
            args |= {"start": start, "end": end}
        res = gate_tb.dispatch("query_metric", args)
        text, is_err = res.content, res.is_error
        _check(is_err and text.startswith("BLOCKED"),
               f"the input guardrail let an out-of-coverage call through: {scope} {start}..{end} -> {text[:60]}")
        passed += 1
    # ...and still serves a legitimate in-coverage call (the coverage check isn't just refuse-all).
    res = gate_tb.dispatch("query_metric", {"metric": "value_moments",
                                            "start": "2026-06-01", "end": "2026-06-30"})
    text, is_err = res.content, res.is_error
    _check(not is_err and "value" in text, "the input guardrail wrongly blocked a valid in-coverage call")
    passed += 1

    # 4. The tool restriction (rrung 4) removes raw SQL entirely — no arbitrary-query escape hatch.
    fenced_names = {t["name"] for t in build_grounding(con, rung=6, guardrails=LADDER[4]).toolbox.specs()}
    _check("run_sql" not in fenced_names, "tool restriction did not remove run_sql")
    _check("query_metric" in fenced_names, "tool restriction removed the governed path too")
    passed += 1
    # Below the tool restriction (R3, coverage check only), raw SQL is present (so the contrast is real).
    r3_names = {t["name"] for t in build_grounding(con, rung=6, guardrails=LADDER[3]).toolbox.specs()}
    _check("run_sql" in r3_names, "run_sql should still exist at R3 (the override path)")
    passed += 1

    # 5. The catalog enum is closed at the coverage check: the model is offered only real metrics.
    qm = next(t for t in gate_tb.specs() if t["name"] == "query_metric")
    enum = qm["input_schema"]["properties"]["metric"].get("enum")
    _check(enum and set(enum) == set(sl.metrics), "query_metric enum is not the exact catalog")
    passed += 1

    return passed


def test_the_evidence_layer_never_reaches_back_into_the_agent():
    """The evidence layer measures the agent, so it must not depend on it.

    Guardrails may consult `evidence/` — `after.py` does, for the rounding-identity test. The
    reverse direction is what would make the instrument part of the thing it measures, and it is
    the kind of rule that survives exactly until someone needs one convenient import. So it is a
    test rather than a paragraph: `evidence/` may see the certified model and a trace, and
    nothing else.

    A trace arrives as plain dicts on purpose. The audit therefore needs no type from `agent/`,
    which is what makes this rule cheap to keep rather than a constant fight."""
    import ast

    forbidden = ("agent", "evals", "cli")
    root = harness_paths.ROOT / "engine" / "src" / "evidence"
    checked = 0
    for path in sorted(root.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                top = (node.module or "").split(".")[0]
            elif isinstance(node, ast.Import):
                top = node.names[0].name.split(".")[0]
            else:
                continue
            _check(top not in forbidden,
                   f"evidence/{path.name} imports {top!r} — the evidence layer decides nothing "
                   "and must not depend on what it measures (docs/ARCHITECTURE.md)")
            checked += 1
    _check(checked >= 3, f"expected the evidence layer's imports, found {checked}")


def test_the_engine_never_imports_the_apparatus():
    """One direction, for every package that would ship.

    `agent/`, `semantic/`, `warehouse/` and `evidence/` are the closure a product installs: the
    agent reaches semantic, semantic reaches warehouse, and guardrails consult evidence. The
    apparatus — `cli/`, `evals/`, `experiments/`, `scratchpad/` — measures that closure and is
    never installed with it. So every edge must point apparatus -> engine, and an edge the other
    way makes the engine uninstallable without the instrument that measures it.

    This generalises the rule above, which enforced the same thing for exactly one of the four.
    There was one violation when it was written: `agent/__init__.py` imported the CLI's trace
    renderer, and the fix was to pass the renderer in rather than reach for it. Every other import
    site already pointed the right way, so the rule describes the code rather than constraining
    it — which is the moment to write a rule down, before the next convenient import.

    Function-local imports count. Deferring an import changes when it fails, not whether the
    dependency exists, and a lazily-imported package is just as absent from a wheel.
    """
    import ast

    # Discovered, not listed. A hardcoded tuple checks the packages that existed when it was written
    # and silently ignores any added (or, as here, extracted) later.
    root = harness_paths.ROOT / "engine" / "src"
    engine = tuple(sorted(d.name for d in root.iterdir()
                          if d.is_dir() and (d / "__init__.py").exists()))
    # Floor was 4 before `warehouse` and `semantic` were extracted to their own top-level packages
    # (each depends only downward — agent -> semantic -> warehouse — so the "no apparatus imports"
    # rule holds there too). agent and evidence remain here; the floor only guards discovery ran.
    _check(len(engine) >= 2, f"expected the engine's packages under {root}, found {engine}")
    # `harness_paths` is in this set because the engine must not know it lives beside an
    # apparatus, let alone where that apparatus keeps its runs.
    apparatus = {"cli", "evals", "experiments", "scratchpad", "tests", "harness_paths"}
    # Per package, not a single total: one large package can satisfy a global floor on its own
    # while another is renamed out from under the test and silently stops being checked.
    # engine/tests/ is checked too, and for the same reason: it travels in the engine's sdist, so
    # a test there that imports the apparatus makes the shipped artefact untestable on its own.
    # This was not covered when the rule was written, and one such test had already moved in.
    targets = {p: root / p for p in engine}
    targets["tests"] = harness_paths.ROOT / "engine" / "tests"
    checked = dict.fromkeys(targets, 0)
    for package, directory in targets.items():
        for path in sorted(directory.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
                if isinstance(node, ast.Import):
                    tops = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    tops = [node.module.split(".")[0]]
                else:
                    continue
                for top in tops:
                    # A test may name its own directory; only cross-boundary imports are the rule.
                    if package == "tests" and top == "tests":
                        continue
                    _check(top not in apparatus,
                           f"{path.relative_to(harness_paths.ROOT)}:{node.lineno} imports {top!r} — the engine "
                           "must not depend on the apparatus that measures it. Pass the thing in "
                           "(see ask_one's `trace` parameter) rather than importing it.")
                    checked[package] += 1
    for package, n in checked.items():
        _check(n >= 5, f"walked only {n} imports in {package}/ — has it moved or been renamed?")


def test_the_cli_imports_what_it_claims_to():
    """Every CLI subcommand imports lazily, inside its handler, so a moved module breaks that one
    command and nothing else — the whole suite stayed green while `bench ask` pointed at a module
    that had been deleted. This resolves every import the CLI declares, at any nesting, and
    checks the names actually exist."""
    import ast
    import importlib
    import inspect

    cli = importlib.import_module("cli.__main__")
    checked = 0
    for node in ast.walk(ast.parse(inspect.getsource(cli))):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        module = importlib.import_module(node.module)
        for alias in node.names:
            _check(hasattr(module, alias.name),
                   f"cli imports {alias.name!r} from {node.module!r}, which does not have it")
            checked += 1
    _check(checked >= 8, f"expected the CLI's imports, found {checked}")


if __name__ == "__main__":
    # `bench test` runs each of these files as a SCRIPT, not under pytest, so a test that is not
    # called here does not run — it only runs for whoever happens to invoke pytest directly. The
    # boundary test below was added and left out of this list, which meant the rule it enforces
    # was enforced nowhere while appearing to be covered.
    test_the_cli_imports_what_it_claims_to()
    test_the_evidence_layer_never_reaches_back_into_the_agent()
    test_the_engine_never_imports_the_apparatus()
    n = prove()
    print(f"OK — {n} structural assertions proved with no LLM.")


def test_structural_guarantees():
    assert prove() > 0
