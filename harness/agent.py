"""The agent loop: a minimal tool-use cycle with self-correction.

Call the model; run the tools it asks for; feed results (including errors, which is
what lets it self-correct) back; stop when it calls final_answer or a cap is hit. This
loop is identical at every rung — only the grounding it receives changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_ABSTAIN_MARKERS = ("cannot answer", "can't answer", "cannot be answered", "don't know",
                    "do not know", "unable to", "not able to", "no data")


def _looks_like_abstain(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in _ABSTAIN_MARKERS)


@dataclass
class Answer:
    question: str
    rung: int
    model: str
    answer: str | None
    explanation: str = ""
    abstained: bool = False
    tool_calls: int = 0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    steps: list = field(default_factory=list)


def run_agent(question: str, grounding, model, max_iters: int = 8) -> Answer:
    messages: list = [{"role": "user", "content": question}]
    in_tok = out_tok = tool_calls = 0
    steps: list = []
    nudges = 0

    def answer(**kw) -> Answer:
        return Answer(question=question, rung=grounding.rung, model=model.spec.name,
                      tool_calls=tool_calls, input_tokens=in_tok, output_tokens=out_tok,
                      steps=steps, **kw)

    for it in range(max_iters):
        resp = model.create(grounding.system, messages, grounding.toolbox.specs())
        u = getattr(resp, "usage", None)
        in_tok += getattr(u, "input_tokens", 0) or 0
        out_tok += getattr(u, "output_tokens", 0) or 0

        if getattr(resp, "stop_reason", None) == "refusal":
            return answer(answer=None, explanation="model refused", abstained=True,
                          iterations=it + 1, error="refusal")

        blocks = list(resp.content)
        messages.append({"role": "assistant", "content": blocks})

        tool_results, final, text_out = [], None, []
        for b in blocks:
            bt = getattr(b, "type", None)
            if bt == "text":
                text_out.append(getattr(b, "text", ""))
            elif bt == "tool_use":
                if b.name == "final_answer":
                    final = b.input or {}
                else:
                    tool_calls += 1
                    content, is_err = grounding.toolbox.dispatch(b.name, b.input or {})
                    steps.append({"tool": b.name, "args": b.input, "error": is_err,
                                  "result": content[:300]})
                    tool_results.append({"type": "tool_result", "tool_use_id": b.id,
                                         "content": content, "is_error": is_err})

        if final is not None:
            ans = str(final.get("answer", "")).strip()
            return answer(answer=ans, explanation=str(final.get("explanation", "")).strip(),
                          abstained=_looks_like_abstain(ans), iterations=it + 1)

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            nudges += 1
            if nudges > 1:
                txt = " ".join(text_out).strip()
                return answer(answer=txt or None, explanation="(never called final_answer)",
                              iterations=it + 1, error="no_final_answer")
            messages.append({"role": "user",
                             "content": "Submit your answer by calling the final_answer tool."})

    return answer(answer=None, explanation="", iterations=max_iters, error="max_iterations")
