"""The model catalog: which models exist, and what they cost.

Data about models, kept apart from the code that talks to them (providers.py). The cost report
needs a price per token and nothing else — it has no business importing three provider SDKs to
get one, which is what a single models.py forced.
"""
from __future__ import annotations

from dataclasses import dataclass


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
    # The lowest reasoning effort this model will accept. The harness's canonical "off" is
    # `none`, and most models take it; gpt-5-mini rejects it outright (400: supported values are
    # minimal, low, medium, high), so it names its own floor here.
    lowest_effort: str = "none"

    def effort_for(self, requested: str) -> str:
        """The effort to actually send for a requested one.

        A model that cannot go as low as asked runs at its floor instead of failing — but the
        caller is told which by reading `.reasoning` back off the model, because reasoning effort
        is a treatment variable and a row claiming `none` for a run that used `minimal` is a lie.
        """
        off = ("none", "off", "disabled")
        return self.lowest_effort if (requested in off and self.lowest_effort not in off) \
            else requested


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
    _spec("gpt-5.6-terra", 2.50, 15.0, price_confirmed=True, use_responses_api=True),
    _spec("gpt-5.4-mini", 0.25, 2.0),
    # OpenAI list price, corroborated across the OpenAI model page + OpenRouter (2026-07-24).
    # Rejects reasoning_effort='none'; `minimal` is its floor. Every stored run of this model
    # used minimal or higher, so the default was never exercised until it 400'd from `bench ask`.
    _spec("gpt-5-mini", 0.25, 2.0, price_confirmed=True, lowest_effort="minimal"),
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
