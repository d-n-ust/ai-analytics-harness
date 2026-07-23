"""The agent loop: a minimal tool-use cycle with self-correction.

Call the model; run the tools it asks for; feed results (including errors, which is
what lets it self-correct) back; stop when it calls a terminal tool or a cap is hit.
This loop is identical at every rung — only the grounding it receives changes.

Every run ends through one of three terminal tools — answer, refuse, clarify — so the
outcome is a typed field on the Answer. There is no phrase-matching: a refusal is a
`refuse` call carrying a coded reason and the named missing thing, never a sentence
someone has to grep for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TERMINAL_TOOLS = ("answer", "refuse", "clarify")


@dataclass
class Answer:
    question: str
    rung: int
    model: str
    answer: str | None
    explanation: str = ""
    outcome: str = "answer"        # answer | refuse | clarify | error
    reason: str | None = None      # refuse only: the coded reason
    missing: str | None = None     # refuse only: what the model says is missing
    abstained: bool = False        # convenience mirror of outcome == "refuse"
    tool_calls: int = 0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    steps: list = field(default_factory=list)


def run_agent(question: str, grounding, model, max_iters: int = 8, verifier_model=None) -> Answer:
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

        blocks = list(resp.content)
        messages.append({"role": "assistant", "content": blocks})

        tool_results, final, text_out = [], None, []
        for b in blocks:
            bt = getattr(b, "type", None)
            if bt == "text":
                text_out.append(getattr(b, "text", ""))
            elif bt == "tool_use":
                if b.name in TERMINAL_TOOLS:
                    final = final or (b.name, b.input or {})
                else:
                    tool_calls += 1
                    content, is_err, values = grounding.toolbox.dispatch(b.name, b.input or {})
                    steps.append({"tool": b.name, "args": b.input, "error": is_err,
                                  "result": content[:300], "result_values": values})
                    tool_results.append({"type": "tool_result", "tool_use_id": b.id,
                                         "content": content, "is_error": is_err})

        if final is not None:
            name, kw = final
            if name == "answer":
                ans_text = str(kw.get("answer", "")).strip()
                ok, reason, missing, explanation = grounding.toolbox.verify_answer(
                    question, ans_text, steps, model, kw.get("source_metric"), kw.get("value"),
                    verifier_model=verifier_model)
                if not ok:                       # R6+: a failed spec check becomes a refusal
                    return answer(answer=None, explanation=explanation, outcome="refuse",
                                  reason=reason, missing=missing, abstained=True, iterations=it + 1)
                return answer(answer=ans_text,
                              explanation=str(kw.get("explanation", "")).strip(),
                              outcome="answer", iterations=it + 1)
            if name == "refuse":
                return answer(answer=None, explanation=str(kw.get("explanation", "")).strip(),
                              outcome="refuse", reason=kw.get("reason"),
                              missing=kw.get("missing"), abstained=True, iterations=it + 1)
            return answer(answer=None, explanation=str(kw.get("question", "")).strip(),
                          outcome="clarify", iterations=it + 1)

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            nudges += 1
            if nudges > 1:
                txt = " ".join(text_out).strip()
                return answer(answer=txt or None, explanation="(never called a terminal tool)",
                              outcome="error", iterations=it + 1, error="no_final_answer")
            messages.append({"role": "user",
                             "content": "Finish by calling one terminal tool: answer, refuse, or clarify."})

    return answer(answer=None, explanation="", outcome="error",
                  iterations=max_iters, error="max_iterations")
