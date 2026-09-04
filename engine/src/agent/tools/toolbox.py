"""Tool, the TOOLS registry, and the Toolbox that dispatches for a rung.

Part of the agent's action space (see tools/__init__.py): each tool appears ONCE, a schema paired
with its handler, returning a ToolResult the guardrails can read typed numbers from.
"""

from __future__ import annotations

import json  # noqa: F401
from collections.abc import Callable
from dataclasses import (
    dataclass,
    replace,  # noqa: F401
)

from semantic import Causality, MetricTree, SemanticError, SemanticLayer, TreeError  # noqa: F401
from warehouse import DEFAULT_MAX_ROWS as MAX_ROWS  # noqa: F401
from warehouse import (  # noqa: F401,E501
    NAMED_PERIODS,
    TIME_GRAINS,
    QueryError,
    describe_table,
    run_query,
    schema_text,
)

from ..core.conversation import ToolResult  # noqa: F401
from ..core.outcomes import REASON_MEANINGS, REFUSAL_REASONS  # noqa: F401
from ..core.protocol import Protocol  # noqa: F401
from ..core.rungs import capabilities  # noqa: F401
from ..guardrails import LADDER, GuardrailSet, action_space, before, disclosure  # noqa: F401
from .definition import *  # noqa: F401,F403
from .governance import *  # noqa: F401,F403
from .query import *  # noqa: F401,F403
from .terminal import *  # noqa: F401,F403
from .tree import *  # noqa: F401,F403


@dataclass(frozen=True)
class Tool:
    """One tool: the schema the model sees and the code that runs it, in one place.

    `run=None` marks a TERMINAL tool — it ends the run, so the agent loop decides what it means
    and there is nothing to dispatch. That is the only legitimate reason for a tool to have no
    handler, and tests/test_semantic.py holds it to that."""

    schema: dict
    run: Callable | None = None

    @property
    def name(self) -> str:
        return self.schema["name"]


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool(_GET_SCHEMA, _get_schema),
    Tool(_DESCRIBE_TABLE, _describe_table),
    Tool(_RUN_SQL, _run_sql),
    Tool(_LIST_METRICS, _list_metrics),
    Tool(_SHOW_ONTOLOGY, _show_metric_ontology),
    Tool(_QUERY_METRIC, _query_metric),
    Tool(_CHECK_METRIC, _check_metric_exists),
    Tool(_CHECK_ANSWERABILITY, _check_answerability),
    Tool(_DEFINE_MEASURE, _define_measure),
    Tool(_CHECK_COVERAGE, _check_coverage),
    Tool(_CHECK_SEGMENT, _check_segment_defined),
    Tool(_CHECK_CAUSAL, _check_causal_evidence),
    Tool(_GET_METRIC_TREE, _get_metric_tree),
    Tool(_DECOMPOSE_CHANGE, _decompose_change),
    Tool(_ANSWER), Tool(_REFUSE), Tool(_CLARIFY),      # terminal: the loop ends the run
]}


class Toolbox:
    """Holds the live warehouse/semantic/tree handles and exposes the tools for a rung.

    `rung` gates grounding (what the agent knows); the `guardrails` set gates reliability
    (what the agent may do about not knowing):
      0 = no refuse tool · 1+ = typed refusal · 2+ = check_* tools callable ·
      3+ = the coverage check (governed calls validated; out-of-coverage /
           undefined requests are blocked by the system, not the model) ·
      4+ = the tool restriction (raw SQL removed, so every data path is a gated governed call).
    The coverage check and tool restriction are structural: they hold regardless of what the model does,
    which is why they can be proven exhaustively without an LLM (see tests/)."""

    def __init__(self, con, rung: int, semantic: SemanticLayer | None = None,
                 tree: MetricTree | None = None, guardrails: GuardrailSet | None = None,
                 protocol: Protocol | None = None, schema: str | None = None, ontology=None):
        self.con = con
        self.rung = rung
        # The complete marts graph, when the grounding built one. `check_answerability` reads it to
        # ground a measure upfront; None leaves that tool a no-op fallback and the gate on its old path.
        self.ontology = ontology
        # The run's model, injected by run_agent. `check_answerability` uses it to DECOMPOSE the
        # measure (the interpretation half) before the graph verifies it; None -> the tool falls back.
        self.model = None
        # The warehouse schema this agent may read, when the study gives its arm one. None means
        # the shared warehouse — every study before per-arm environments existed. When it is set,
        # `run_sql` refuses any statement naming another schema: `search_path` hides the others,
        # and only this forbids them.
        self.schema = schema
        # GuardrailSet is the one primitive: which reliability guardrails are on. A ladder preset
        # (LADDER[n]) and an ablation cell are both just a GuardrailSet set; every guardrail below reads
        # from it, so a cell is expressible and self-describing. Default R1 (abstention).
        self.g = guardrails if guardrails is not None else LADDER[1]
        # What the answer must DECLARE — a peer of the guardrail set, not a part of it. It gates
        # fields on the answer tool the way the set gates whole tools.
        self.p = protocol if protocol is not None else Protocol()
        self.semantic = semantic
        self.tree = tree

    def specs(self, terminal_only: bool = False, record=None) -> list[dict]:
        """The action space for this configuration — assembled by the ACTION_SPACE guardrails,
        which is where the ladder is legible."""
        return action_space.offer(TOOLS, self.rung, self.g, self.semantic, self.tree,
                                  protocol=self.p, terminal_only=terminal_only, record=record,
                                  ontology=self.ontology)

    def dispatch(self, name: str, args: dict) -> ToolResult:
        """Run one tool. Errors come back as the DB/semantic message rather than as exceptions,
        so the model is told what went wrong and can correct itself — a crashed run is a lost
        measurement, which is worse than a wrong answer because it looks like neither."""
        tool = TOOLS.get(name)
        if tool is None or tool.run is None:
            return ToolResult(f"Unknown tool {name!r}.", is_error=True)
        # Every call passes the BEFORE guardrails and every result passes DISCLOSURE, rather than
        # each handler remembering to ask. A tool added later is guarded by existing; for a call
        # with no scope to check both are no-ops.
        acts: list = []
        verdict = before.check(self.semantic, self.g, args, record=acts)
        if not verdict.allowed:
            return ToolResult(verdict.detail, is_error=True, reason=verdict.reason,
                              blocked_by=verdict.guardrail, acts=tuple(acts))
        try:
            result = disclosure.annotate(tool.run(self, args), args, self.semantic, self.g,
                                         record=acts)
            return replace(result, acts=tuple(acts))
        except (QueryError, SemanticError, TreeError) as exc:
            return ToolResult(f"Error: {exc}", is_error=True, acts=tuple(acts))
        except KeyError as exc:
            return ToolResult(f"Error: missing argument {exc}", is_error=True, acts=tuple(acts))
