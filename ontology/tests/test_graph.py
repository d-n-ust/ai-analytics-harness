"""The marts ontology, proven without an LLM: the graph is generated and verified against
information_schema, render asserts the closed-world stance, verify() decides existence
deterministically, and fingerprint() moves iff the structure moves.

The interpretive half (decomposing a measure into ingredients) is the model's and lives in the
agent; here we test only what the module owns — the deterministic seam.
"""
import duckdb

from ontology import MartsOntology

ENTITY_TABLES = {"user": ("dim_users", []),
                 "activity": ("fct_user_days", ["value_moments", "app_opens"])}
METRICS = {"active_users": "distinct accounts with activity, excluding internal"}


def _ontology():
    con = duckdb.connect()
    con.execute("create schema m")
    con.execute("create table m.dim_users(user_id int, signup_date date, channel varchar, is_internal boolean)")
    con.execute("create table m.fct_user_days(user_id int, active_date date, value_moments int, app_opens int)")
    return MartsOntology.build(con, "m", ENTITY_TABLES, METRICS,
                              relationships=[("activity", "user", "performed_by user_id")],
                              measure_semantics={"value_moments": "count of completed habits",
                                                 "app_opens": "count of app-open events"})


def main() -> None:
    ont = _ontology()

    # 1. Generated from information_schema: every column is a node, nothing more, nothing absent.
    assert "user.signup_date" in ont.nodes
    assert "user.is_internal" in ont.nodes
    assert "activity.value_moments" in ont.nodes and "activity.app_opens" in ont.nodes
    assert "metric.active_users" in ont.nodes
    assert "activity.duration" not in ont.nodes          # never captured -> simply not a node
    assert "user.dark_mode" not in ont.nodes
    # attributes are ALL non-measure columns (complete present), measures are the declared ones
    assert set(ont.entities["activity"]["attributes"]) == {"user_id", "active_date"}
    assert ont.entities["activity"]["measures"] == ["value_moments", "app_opens"]

    # 2. render asserts the closed-world stance and describes measures positively.
    r = ont.render()
    assert "CLOSED WORLD" in r and "COMPLETE" in r
    assert "count of app-open events" in r               # positive semantics, not "not a duration"
    assert "no duration" not in r.lower() and "no screen" not in r.lower()   # no enumerated absence

    # 3. verify() — the deterministic seam. The model proposes; the graph decides existence.
    assert ont.verify("governed", metric="active_users")[0] == "instrumented"
    assert ont.verify("governed", metric="retention")[0] == "uninstrumented"          # fake metric
    assert ont.verify("computable", ingredients=["user.signup_date", "activity.active_date"])[0] == "computable"
    assert ont.verify("computable", ingredients=["activity.duration"])[0] == "uninstrumented"  # absent
    # a join key is a relationship the graph already carries -> not required as an ingredient node
    assert ont.verify("computable", ingredients=["user.signup_date", "activity.user_id"])[0] == "computable"
    assert ont.verify("uninstrumented")[0] == "uninstrumented"

    # 4. build fails loudly when a declared measure is not a real column (graph stays honest).
    try:
        con = duckdb.connect(); con.execute("create schema m"); con.execute("create table m.t(a int)")
        MartsOntology.build(con, "m", {"e": ("t", ["not_a_column"])}, {})
        raise AssertionError("build should reject a measure that is not a column")
    except ValueError:
        pass

    # 5. fingerprint is stable and moves with the structure.
    assert ont.fingerprint() == _ontology().fingerprint()
    assert ont.fingerprint().startswith("sha256:")
    con = duckdb.connect(); con.execute("create schema m")
    con.execute("create table m.dim_users(user_id int, signup_date date, channel varchar, is_internal boolean, plan varchar)")
    con.execute("create table m.fct_user_days(user_id int, active_date date, value_moments int, app_opens int)")
    changed = MartsOntology.build(con, "m", ENTITY_TABLES, METRICS)
    assert changed.fingerprint() != ont.fingerprint()    # a new column changed the present

    print("OK - ontology graph: generated from information_schema, CWA-only (no enumerated absence), "
          "verify() decides existence, build stays honest, fingerprint tracks the structure.")


if __name__ == "__main__":
    main()
