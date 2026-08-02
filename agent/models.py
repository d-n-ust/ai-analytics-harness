"""The model catalog: which models exist, and what they cost.

Data about models, kept apart from the code that talks to them (providers.py). The cost report
needs a price per token and nothing else — it has no business importing three provider SDKs to
get one, which is what a single models.py forced.
"""
from __future__ import annotations

from dataclasses import dataclass

# Reasoning effort, weakest to strongest. The canonical vocabulary; a model accepts some slice
# of it, and `off`/`disabled` are aliases callers use for the weakest.
EFFORT_LADDER = ("none", "minimal", "low", "medium", "high", "xhigh")


@dataclass(frozen=True)
class ModelSpec:
    name: str
    model_id: str
    input_price: float      # USD per 1M input tokens
    output_price: float     # USD per 1M output tokens
    provider: str = "anthropic"
    thinking: dict | None = None   # Anthropic only
    # OpenAI only: whether the API accepts reasoning_effort (gpt-4.x predates it).
    supports_reasoning_effort: bool = True
    # OpenAI-compatible providers (e.g. DeepSeek) reuse the OpenAI wrapper but talk to a
    # different endpoint/key. base_url=None means the OpenAI default endpoint.
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    # False = the price above is a PLACEHOLDER (starred as estimated in the cost report).
    price_confirmed: bool = False
    # gpt-5.6 rejects function tools + reasoning_effort on /v1/chat/completions; it needs the
    # Responses API (/v1/responses). True routes this model's calls through _create_responses.
    use_responses_api: bool = False
    # The reasoning efforts this model ACCEPTS, in ladder order. Not every model has the same
    # ladder and the difference is not just where the floor is: gpt-5-mini takes
    # minimal/low/medium/high and rejects `none`; gpt-5.6-terra takes none/low/medium/high/xhigh
    # and rejects `minimal`. Neither is a prefix of the other, so a floor alone cannot describe
    # them — asking terra for `minimal` is not "below its floor", it is a word it does not know,
    # and it 400s. That killed 342 rows of a sweep before this was a list.
    efforts: tuple[str, ...] = EFFORT_LADDER

    def effort_for(self, requested: str) -> str:
        """The effort to actually SEND for a requested one.

        A model that does not accept the requested effort runs at its nearest instead of failing
        — but the caller is told which, by reading `.reasoning` back off the model, because
        reasoning effort is a treatment variable and a row claiming `minimal` for a run that sent
        `none` is a lie.
        """
        if requested in self.efforts:
            return requested
        want = EFFORT_LADDER.index(requested) if requested in EFFORT_LADDER else 0
        # Nearest on the canonical ladder, so a request below the floor lands on the floor and one
        # above the ceiling lands on the ceiling, rather than either becoming a 400.
        return min(self.efforts, key=lambda e: abs(EFFORT_LADDER.index(e) - want))


def _spec(model_id: str, inp: float, out: float, provider: str = "openai",
          thinking: dict | None = None, **kw) -> ModelSpec:
    return ModelSpec(model_id, model_id, inp, out, provider, thinking, **kw)


# Keyed by the full model id — the same string appears on the CLI, in every result
# row, and in every summary, so nothing ever needs an alias decoder ring.
MODEL_SPECS: dict[str, ModelSpec] = {spec.model_id: spec for spec in [
    # Sonnet 5 runs adaptive thinking unless disabled; Haiku 4.5 has none to disable.
    _spec("claude-haiku-4-5", 1.0, 5.0, "anthropic"),
    _spec("claude-sonnet-5", 3.0, 15.0, "anthropic", {"type": "disabled"}),
    # OpenAI. Prices are placeholders (gpt-5.4-mini is far cheaper than the flagship).
    # OpenAI list price, corroborated across aipricing.guru + pricepertoken + OpenRouter (2026-07-25);
    # cached input reads at $0.25/1M (10% of input), captured per-call so USD is real, not an upper bound.
    _spec("gpt-5.6-terra", 2.50, 15.0, price_confirmed=True, use_responses_api=True,
          efforts=("none", "low", "medium", "high", "xhigh")),   # 400s on `minimal`
    # Same family as terra, so same API surface and the same effort ladder (no `minimal`).
    # Price is OpenRouter's published base tier (2026-07-28), ONE source rather than the three
    # terra and gpt-5-mini were corroborated against, so it stays unconfirmed and the cost report
    # stars it. Both models also carry a long-context tier that doubles input above 272k prompt
    # tokens; this bench runs ~6k per call, so the base rate is the one that applies.
    _spec("gpt-5.6-sol", 5.00, 30.0, use_responses_api=True,
          efforts=("none", "low", "medium", "high", "xhigh")),   # 400s on `minimal`
    # Responses API for the same reason terra and sol need it: /v1/chat/completions now rejects
    # function tools together with reasoning_effort for this model. It fails as an intermittent
    # 400 rather than a clean one — a 57-question sweep lost 25 rows to it, each stored as an
    # `error` outcome, which is a lost measurement rather than a model behaviour and is invisible
    # in any rate that divides by answered questions. This model is half the write-up pair, so
    # every stored run of it should be checked for error rows before its numbers are believed.
    _spec("gpt-5.4-mini", 0.25, 2.0, use_responses_api=True),
    # OpenAI list price, corroborated across the OpenAI model page + OpenRouter (2026-07-24).
    # Rejects reasoning_effort='none'; `minimal` is its floor. Every stored run of this model
    # used minimal or higher, so the default was never exercised until it 400'd from `bench ask`.
    _spec("gpt-5-mini", 0.25, 2.0, price_confirmed=True,
          efforts=("minimal", "low", "medium", "high")),   # 400s on `none`
    _spec("gpt-5.6-luna", 1.0, 8.0),  # price a placeholder; tier unknown
    # Cheap legacy model for pilot runs.
    _spec("gpt-4.1-mini", 0.4, 1.6, supports_reasoning_effort=False),
    # DeepSeek V4 (OpenAI-compatible endpoint). Reasoning is a thinking on/off toggle
    # plus reasoning_effort in {high,max}; our 'none' = non-thinking mode — see
    # OpenAIModel._deepseek_reasoning. Prices are DeepSeek's real published rates
    # (USD / 1M tokens, cache-miss input). Ids verified live against /models 2026-07-23.
    _spec("deepseek-v4-flash", 0.14, 0.28, provider="deepseek",
          base_url="https://api.deepseek.com", api_key_env="DEEPSEEK_API_KEY", price_confirmed=True),
    _spec("deepseek-v4-pro", 0.435, 0.87, provider="deepseek",
          base_url="https://api.deepseek.com", api_key_env="DEEPSEEK_API_KEY", price_confirmed=True),
]}
