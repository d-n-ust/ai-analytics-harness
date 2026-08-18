# preflight as a guardrail (CI / pre-commit)

`preflight scan --fail-on high` exits non-zero when a dangerous collision exists, so a change that
introduces one fails the build. The whole job is `dbt parse` (your own dbt) then one `preflight scan`
line — no warehouse connection required.

## GitHub Actions

A composite action ships with the package. Point it at your analytics repo:

```yaml
# .github/workflows/preflight.yml
name: preflight
on: [pull_request]
jobs:
  ambiguity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: d-n-ust/ai-analytics-harness/preflight@master   # becomes d-n-ust/preflight@v1 once extracted
        with:
          path: .
          gate: embeddings          # best results; use 'lexical' to skip torch
          fail-on: high
```

Until `preflight` is on PyPI, install it with the VCS form:
`preflight[embeddings] @ git+https://github.com/d-n-ust/ai-analytics-harness@master#subdirectory=preflight`.

## pre-commit

Once `preflight` is its own repo, use the packaged hook:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/d-n-ust/preflight
    rev: v0.1.0
    hooks: [{ id: preflight }]
```

Today, from any environment where `preflight` is installed, use a local hook:

```yaml
repos:
  - repo: local
    hooks:
      - id: preflight
        name: preflight ambiguity scan
        entry: preflight scan . --dialect dbt-manifest --fail-on high
        language: system
        pass_filenames: false
```

## The gate in CI

Install `[embeddings]` in CI too, so it scores on the sharper, validated gate rather than the lexical
fallback. If you want CI to *fail* rather than silently degrade when the extra is missing, use
`--gate embeddings` (which errors) instead of the default `auto`. Details: [gate.md](gate.md).
