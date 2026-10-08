"""Read one question and print the reader's raw answers (a debugging aid; not part of the audit)."""
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "01_parameter_grounding"))
import run as R  # noqa: E402
from agent.guardrails import decisions, parse_cell
from agent.runtime.grounding import build_grounding
from warehouse.warehouse import open_warehouse

con = open_warehouse(create_star_views=True)
R.fixture_build.build(con, drop=True)
cursor = R.scoped_cursor(con)
semantic = build_grounding(cursor, rung=R.RUNG, spec_path=R.LAYER, engine="metricflow", semantic_layer=True,
                           guardrails=parse_cell("R4"), schema=R.MARTS).toolbox.semantic
for q in sys.argv[1:]:
    cache: dict = {}
    reading, cost = decisions.reading_for(q, "app_opens", semantic, cursor, R.GOVERNANCE, cache)
    print("Q:", q)
    for v in cache.values():
        ans = v.get("answers") if isinstance(v, dict) else None
        for k, a in (ans or {}).items():
            if k.split(":")[0] in ("shape", "breakdown", "time_grain", "outside") or (k.startswith("period:") and a.get("noul", 0) > 0.15):
                print("  ", k, json.dumps(a)[:200])
    print("  periods", reading["periods"], "group_by", reading["group_by"], "grain", reading["grain"])
    for d in reading["decisions"]:
        print("   decision", json.dumps(d, default=str)[:220])
