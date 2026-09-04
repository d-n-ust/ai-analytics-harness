"""The agent's action space: every tool, and the code that runs it.

Each tool appears ONCE, as a schema paired with its handler — they used to be three places apart
and they drifted (a handler reading an argument its schema never offered). The families group by
domain: query (the data plane), governance (answerability/coverage/segment/causal), definition
(the spec pipeline's tool), tree, and the terminal tools the loop owns. toolbox.py assembles the
registry and dispatches for a rung; which tools are OFFERED stays the action-space guardrails' job
(guardrails/action_space.py), so the ladder reads in one place.
"""

from ._shared import _fmt_rows, _labelled, _measure_values, _time_scope_line  # noqa: F401
from .definition import *  # noqa: F401,F403
from .governance import *  # noqa: F401,F403
from .query import *  # noqa: F401,F403
from .terminal import *  # noqa: F401,F403
from .toolbox import TOOLS, Tool, Toolbox  # noqa: F401
from .tree import *  # noqa: F401,F403
