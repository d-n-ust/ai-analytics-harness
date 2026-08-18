#!/usr/bin/env bash
# preflight-dbt — scan a dbt project for grounding ambiguity in one command.
#
# It compiles the project's manifest with a throwaway DuckDB profile, then runs
# `preflight scan --dialect dbt-manifest` on it. `dbt parse` never connects to a
# warehouse, so a DuckDB profile stands in for Snowflake/BigQuery/Redshift/etc —
# the real target does not matter and nothing here touches your ~/.dbt or your
# project's profiles.yml.
#
# Usage:
#   preflight-dbt.sh [PROJECT_DIR] [extra preflight-scan args...]
#
#   preflight-dbt.sh                     # scan the dbt project in the current dir
#   preflight-dbt.sh path/to/project     # scan another project
#   preflight-dbt.sh . --detail          # forward flags to `preflight scan`
#   preflight-dbt.sh . --fail-on high    # e.g. as a CI gate
#
# Requirements: uv and git on PATH, and `preflight` installed (uv tool install .).
# `dbt deps` needs network if the project has packages. Override the dbt toolchain
# with DBT_PKGS (default: "dbt-core dbt-duckdb", i.e. latest).

set -euo pipefail

# ---- args: first non-flag arg is the project dir; the rest go to `preflight scan` ----
PROJECT_DIR="."
if [ "${1:-}" ] && [ "${1#-}" = "$1" ]; then   # $1 exists and does not start with '-'
  PROJECT_DIR="$1"; shift
fi
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"       # absolute, and fail early if it does not exist

[ -f "$PROJECT_DIR/dbt_project.yml" ] || {
  echo "preflight-dbt: no dbt_project.yml in '$PROJECT_DIR' — is this a dbt project?" >&2; exit 1; }

# ---- the profile name dbt expects (matches `profile:` in dbt_project.yml) ----
PROFILE="$(sed -nE "s/^profile:[[:space:]]*[\"']?([A-Za-z0-9_-]+).*/\1/p" \
                 "$PROJECT_DIR/dbt_project.yml" | head -1)"
[ -n "$PROFILE" ] || {
  echo "preflight-dbt: could not read 'profile:' from dbt_project.yml" >&2; exit 1; }

# ---- a throwaway DuckDB profile + toolchain in a temp dir, cleaned up on exit ----
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cat > "$WORK/profiles.yml" <<YAML
$PROFILE:
  target: dev
  outputs:
    dev: { type: duckdb, path: "$WORK/scratch.duckdb" }
YAML

echo "preflight-dbt: project '$PROJECT_DIR' (profile: $PROFILE)"
echo "preflight-dbt: installing dbt (${DBT_PKGS:-dbt-core dbt-duckdb}) ..."
uv venv "$WORK/venv" >/dev/null 2>&1
# shellcheck disable=SC2086
uv pip install --python "$WORK/venv" --quiet ${DBT_PKGS:-dbt-core dbt-duckdb}
DBT="$WORK/venv/bin/dbt"

# ---- deps (only if the project declares any) + parse -> target/manifest.json ----
if [ -f "$PROJECT_DIR/packages.yml" ] || [ -f "$PROJECT_DIR/dependencies.yml" ]; then
  echo "preflight-dbt: dbt deps ..."
  "$DBT" deps --project-dir "$PROJECT_DIR" --profiles-dir "$WORK" >/dev/null
fi
echo "preflight-dbt: dbt parse ..."
"$DBT" parse --project-dir "$PROJECT_DIR" --profiles-dir "$WORK" >/dev/null

# ---- scan ----
if command -v preflight >/dev/null 2>&1; then
  echo "preflight-dbt: scanning ..."; echo
  exec preflight scan "$PROJECT_DIR" --dialect dbt-manifest "$@"
fi
echo
echo "preflight-dbt: manifest ready at $PROJECT_DIR/target/manifest.json"
echo "  'preflight' is not on PATH. Install it (uv tool install /path/to/preflight), then:"
echo "  preflight scan '$PROJECT_DIR' --dialect dbt-manifest ${*:-}"
