"""Native dbt: scan a whole project from its compiled `target/manifest.json`.

This is the cross-layer entry point preflight is built for. A dbt project holds all three grounding
layers in one artifact once parsed: the **semantic layer** (`semantic_models` + `metrics`, dbt 1.6+),
the **warehouse** (model `nodes` with their columns and data types), and the **docs** (the
`description` on every model and column). One `dbt parse` (no warehouse connection needed) produces the
manifest; preflight reads it and reports confusions within and across those layers.

    preflight scan path/to/dbt_project --dialect dbt-manifest      # finds target/manifest.json
    preflight scan path/to/target/manifest.json --dialect dbt-manifest

Every finding is cited back to the real dbt source file and line (`models/marts/orders.yml:42`), not
to the manifest: the manifest records each definition's `original_file_path` (and, for the columns
documented in a schema file, the model's `patch_path`), and the project root is recovered from the
manifest's own location, so the citation points at the file an analytics engineer edits. When the
source files are not shipped alongside the manifest, the finding still reports; only the line citation
is omitted.

The manifest is read defensively — only the few stable fields are touched — so it survives the schema
drift across manifest versions.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .adapters import line_of_definition
from .metricflow import facts_from_metricflow
from .model import GroundingFact, Source


def _resolve(path: str | Path) -> tuple[Path, Path]:
    """(manifest.json, project_root). Accepts the manifest file, a `target/` dir, or a project dir.
    The root is where dbt's relative `original_file_path`/`patch_path` are anchored: the parent of
    `target/` for a compiled manifest, else the given directory.

    Raises FileNotFoundError with an actionable message when no manifest is present. The common cause
    is scanning a project before `dbt parse` has produced `target/manifest.json`; a bare directory read
    would otherwise fail deep inside with an opaque IsADirectoryError."""
    p = Path(path)
    if p.is_dir():
        for cand in (p / "target" / "manifest.json", p / "manifest.json"):
            if cand.is_file():
                p = cand
                break
        else:
            raise FileNotFoundError(
                f"no dbt manifest under '{Path(path)}' (looked for target/manifest.json). "
                f"Run `dbt parse` in the project first to generate it.")
    elif not p.is_file():
        raise FileNotFoundError(
            f"no such manifest: '{p}'. Point --dialect dbt-manifest at a dbt project directory "
            f"or a target/manifest.json file.")
    root = p.parent.parent if p.parent.name == "target" else p.parent
    return p, root


def _strip_package(patch_path: str | None) -> str | None:
    """A model's `patch_path` is `<package>://models/…/schema.yml`; the file lives at that relative
    path under the project root. Returns the relative path, or None if there is no patch file."""
    if not patch_path:
        return None
    return patch_path.split("://", 1)[-1]


class _Citer:
    """Resolves a (relative source file, label) to a `Source(path, line)`, reading each file at most
    once. Returns None when the file is absent (manifest shipped without sources) or the label is not
    found — the caller then emits an uncited fact rather than a wrong line."""

    def __init__(self, root: Path):
        self._root = root
        self._text: dict[Path, str | None] = {}

    def _read(self, rel: str) -> str | None:
        abs_path = self._root / rel
        if abs_path not in self._text:
            try:
                self._text[abs_path] = abs_path.read_text()
            except OSError:
                self._text[abs_path] = None
        return self._text[abs_path]

    def cite(self, rel: str | None, label: str) -> Source | None:
        if not rel:
            return None
        text = self._read(rel)
        if text is None:
            return None
        ln = line_of_definition(text, label)
        return Source(str(self._root / rel), ln) if ln else None


def _semantic_layer(manifest: dict, citer: _Citer) -> list[GroundingFact]:
    """The dbt Semantic Layer, mapped onto the MetricFlow adapter's shape. `semantic_models` and
    `metrics` are dicts keyed by unique_id in the manifest; the values carry the same fields the raw
    YAML does, with two differences normalised here: the base table lives in `node_relation` (not
    `model:`), and a metric's filter is a list of where-templates (not a single Jinja string).

    Each resulting fact is cited back to the YAML that defines the metric, or, for an orphan measure,
    the semantic model's own file."""
    sems, src_of_label = [], {}
    for sm in (manifest.get("semantic_models") or {}).values():
        sm = dict(sm)
        nr = sm.get("node_relation") or {}
        sm["model"] = nr.get("alias") or nr.get("relation_name") or sm.get("name")
        sems.append(sm)
        for meas in sm.get("measures") or []:                 # a measure is cited to its semantic model's file
            src_of_label[meas.get("name")] = sm.get("original_file_path")

    mets = []
    for mt in (manifest.get("metrics") or {}).values():
        mt = dict(mt)
        f = mt.get("filter")
        if isinstance(f, dict):                               # {"where_filters": [{"where_sql_template": "..."}]}
            wf = f.get("where_filters") or []
            mt["filter"] = " and ".join(w.get("where_sql_template", "") for w in wf) or None
        mets.append(mt)
        src_of_label[mt.get("name")] = mt.get("original_file_path")   # a metric's own file wins over the measure's

    facts = facts_from_metricflow(sems, mets)
    return [replace(f, source=citer.cite(src_of_label.get(f.label), f.label)) for f in facts]


def _warehouse_and_docs(manifest: dict, citer: _Citer) -> list[GroundingFact]:
    """Model nodes become table + column grounding facts; each carries its dbt `description`, so a
    description that names a term two ways, or that clashes with a metric, surfaces cross-layer.
    Columns are documented in the model's schema file (`patch_path`), so that is where they are
    cited; the table itself is cited to the same schema file, falling back to the model SQL."""
    facts: list[GroundingFact] = []
    for node in (manifest.get("nodes") or {}).values():
        if node.get("resource_type") != "model":
            continue
        table = node.get("name")
        if not table:
            continue
        patch = _strip_package(node.get("patch_path"))
        facts.append(GroundingFact(
            id=f"wh:{table}", label=table, layer="warehouse", kind="table", base=table,
            text=f"table {table}. {node.get('description', '')}".strip(),
            source=citer.cite(patch, table)))
        for col in (node.get("columns") or {}).values():
            cname = col.get("name")
            if not cname:
                continue
            dtype = col.get("data_type") or ""
            facts.append(GroundingFact(
                id=f"wh:{table}.{cname}", label=str(cname).lower(), layer="warehouse", kind="column",
                base=table, measure=str(cname).lower(),
                text=f"{cname} {dtype}. {col.get('description', '')}".strip(),
                source=citer.cite(patch, str(cname))))
    return facts


def load_dbt_manifest(path: str | Path) -> list[GroundingFact]:
    """Every grounding fact across a dbt project's three layers, from its `manifest.json`, each cited
    back to the source file it was defined in."""
    manifest_file, root = _resolve(path)
    manifest = json.loads(manifest_file.read_text())
    citer = _Citer(root)
    return _semantic_layer(manifest, citer) + _warehouse_and_docs(manifest, citer)
