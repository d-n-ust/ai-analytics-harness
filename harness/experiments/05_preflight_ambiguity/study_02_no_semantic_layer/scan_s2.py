#!/usr/bin/env python3
"""Static preflight scan of the two study-02 warehouses. Verified result: **no findings on either
arm**, and that is the point this script documents.

Study 01 persisted its per-environment scan in `../study_01_governed_layer/scan.md`; this script is
the same static side for study 02, and it comes back empty because the before-warehouse's ambiguity
is not written down anywhere a definition scanner could read it: `is_internal` vs `is_test` share no
name similarity and carry no docs, `mrr` does not exist as a column (nothing collides with
`billed_amount`), and `moments` recurs in only two tables, below the overload threshold. Static
prediction of the runtime harm is study 01's claim; study 02 measures the repair. See the README's
"Static scan" section.

The DDL below mirrors `warehouses.py` column for column and comment for comment: the views become
CREATE TABLE statements because preflight's warehouse adapter reads DDL text, and the DuckDB
`COMMENT ON` strings become inline `--` comments (same idiom as study 01's `warehouse.sql`).

    python scan_s2.py          # writes scan.md next to this file

Gate is lexical, matching the study-01 scan header, so the two static sides are comparable.
"""
from __future__ import annotations

import pathlib
import tempfile

from preflight import adapt_warehouse, detect_collisions

# ---- s2_before: raw, confusable columns, thin docs (mirrors warehouses.py) ----
BEFORE_SQL = """\
CREATE TABLE subscriptions (
    subscription_id INT,
    user_id INT,
    billed_amount DOUBLE,
    plan VARCHAR,
    active BOOLEAN,
    status VARCHAR
);

CREATE TABLE users (
    user_id INT,
    is_internal BOOLEAN,          -- internal flag
    is_test BOOLEAN,
    signup_date DATE,
    created_at TIMESTAMP
);

CREATE TABLE users_v2 (
    user_id INT,
    is_internal BOOLEAN,
    signup_date DATE
);

CREATE TABLE subscriptions_2026_03 (
    subscription_id INT,
    user_id INT,
    billed_amount DOUBLE,
    plan VARCHAR,
    status VARCHAR
);

CREATE TABLE activity (
    user_id INT,
    active_date DATE,
    moments INT,
    is_internal BOOLEAN
);

CREATE TABLE daily_rollup (
    user_id INT,
    day DATE,
    moments INT
);

CREATE TABLE marketing (
    spend_date DATE,
    channel VARCHAR,
    spend DOUBLE
);
"""

# ---- s2_after: one column per concept, scope stated in the docs (mirrors warehouses.py) ----
AFTER_SQL = """\
CREATE TABLE dim_subscriptions (
    subscription_id INT,
    user_id INT,
    mrr DOUBLE,                   -- Monthly recurring revenue: annual plans divided by 12. Filter is_active for the current book, and join dim_users to exclude staff/test accounts (NOT is_internal).
    net_revenue DOUBLE,           -- Recognised subscription revenue. Filter is_active for the current book, and join dim_users to exclude staff/test accounts (NOT is_internal).
    plan VARCHAR,
    status VARCHAR,               -- Subscription state (active/canceled/paused/refunded), rebuilt fresh from source on every load - authoritative.
    is_active BOOLEAN             -- TRUE when the term is currently active (status active, no end recorded). THE flag for every current-book question.
);

CREATE TABLE dim_users (
    user_id INT,
    is_internal BOOLEAN,          -- True for staff and test accounts. Exclude (NOT is_internal) from every metric, revenue included.
    signup_date DATE,             -- The date the user actually joined. Use this, not created_at, for signup and cohort questions.
    created_at TIMESTAMP          -- Row creation timestamp. A 2026-05-15 bulk import created older accounts late; use signup_date for cohorts.
);

CREATE TABLE fct_activity (
    user_id INT,
    active_date DATE,
    moments INT,                  -- Value moments (completed habits). Sum for value-moment volume.
    is_internal BOOLEAN           -- True for staff and test accounts. Exclude (NOT is_internal) from every activity metric.
);

CREATE TABLE fct_marketing (
    spend_date DATE,
    channel VARCHAR,
    spend DOUBLE
);
"""


def scan_one(name: str, ddl: str) -> tuple[str, list]:
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write(ddl)
        path = f.name
    facts = adapt_warehouse(pathlib.Path(path))
    findings = detect_collisions(facts, gate="lexical")
    return name, findings


def main() -> None:
    lines = ["```", "", "  STUDY-02 STATIC SCAN            gate: lexical", "  " + "-" * 60]
    details: list[str] = []
    for name, ddl in (("s2_before", BEFORE_SQL), ("s2_after", AFTER_SQL)):
        _, findings = scan_one(name, ddl)
        by = {"high": 0, "medium": 0, "low": 0}
        for f in findings:
            by[str(f.danger)] = by.get(str(f.danger), 0) + 1
        lines.append(
            f"  {name:<12} {len(findings):>2} confusions   "
            f"({by['high']} high {by['medium']} med {by['low']} low)"
        )
        details.append(f"\n==== {name} " + "=" * 46)
        if not findings:
            details.append("  (no findings)")
        for f in findings:
            labels = "  ~  ".join(it.label for it in f.items)
            details.append(f"  {str(f.danger)[0].upper()} {f.type:<22} {labels}")
            details.append(f"      {f.note}")
    lines += details + ["", "```"]
    out = pathlib.Path(__file__).parent / "scan.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
