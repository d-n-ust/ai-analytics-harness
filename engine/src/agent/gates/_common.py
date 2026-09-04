"""Shared constants of the gate pipeline and the loop.

One grace turn, and the correction budget every output gate draws on — module-level and imported
by both the loop (which enforces it) and the gates (the binding check constructs instead of
handing back once the budget is spent), so there is exactly one number."""

GRACE, MAX_CORRECTIONS = 1, 2
