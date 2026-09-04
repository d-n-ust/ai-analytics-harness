"""The imperative shell: the loop, the providers, grounding assembly, and the definition
sub-agent — everything with I/O or a model call. Imports flow downward only: runtime may import
core, gates, guardrails and tools; nothing below imports runtime."""
