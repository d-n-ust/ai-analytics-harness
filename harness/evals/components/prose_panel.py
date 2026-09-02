"""Label the judge's PROSE decisions with a three-lens panel, and escalate what it splits on.

`verifier_vs_gold.py` scores every judged row an independent gold can settle — a numeric answer
against `gold_sql`, or any number served for a question that has no correct number. What it
cannot see is the prose set: diagnostic and keyword questions, where the answer is an argument
rather than a figure. Those are exactly the rows the trajectory judge was hardest to get right,
so leaving them unscored leaves the judge's error rate unknown where it matters most.

Three panelists label each decision INDEPENDENTLY and BLIND — none is shown the judge's verdict,
or the others'. They are given deliberately different lenses, because three runs of one lens is
one opinion with error bars, not a panel:

    strict      would a careful analyst have SERVED this, as written?
    pragmatic   would the person who asked be well served by it?
    skeptical   what is wrong with it, and is that disqualifying?

Unanimous verdicts become labels. **Any split is escalated to a human** rather than resolved by
majority: a 2-1 is the panel telling you the case is genuinely arguable, and averaging that away
is how a validation set comes to encode a coin flip as ground truth.

    sample:  uv run python harness/evals/components/prose_panel.py sample runs/latest/raw.jsonl
    review:  the escalations are written to evals/labels/prose_panel_escalations.yml
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from agent.core.conversation import Conversation

LABELS_DIR = Path(__file__).resolve().parent.parent / "labels"
OUT = LABELS_DIR / "prose_panel.json"
ESCALATIONS = LABELS_DIR / "prose_panel_escalations.yml"

_LENS = {
    "strict": ("You are a careful senior analyst reviewing whether an answer should have been "
               "SERVED to a business stakeholder as written. Hold it to what it actually says, "
               "not to what it might have meant."),
    "pragmatic": ("You are the person who asked this question. Judge whether this answer leaves "
                  "you better informed and able to act, even if it is imperfect or incomplete."),
    "skeptical": ("You are looking for what is wrong with this answer — an unsupported causal "
                  "claim, a figure that does not mean what it is said to mean, a driver named "
                  "that the data does not identify. Then decide whether what you found is "
                  "DISQUALIFYING or merely imperfect."),
}

_SYSTEM = (
    "{lens}\n\n"
    "You are NOT being asked whether the answer is well written, complete, or how you would have "
    "phrased it. One question only: should this answer have been served, or should the system "
    "have refused to answer?\n\n"
    "Serve it if it is substantively right and its claims are supported by what was computed. "
    "Refuse it if it asserts something the data does not support, names a cause that is not a "
    "cause, or reports a figure that does not mean what the sentence says it means.\n\n"
    "AN ASSERTION IS NOT A SUGGESTION. 'X caused Y' is a claim about the world and must be "
    "supported. 'Investigate X' is a claim about what to do next, and is not — you investigate "
    "precisely where you do not yet know. Do not refuse an answer for recommending a next step, "
    "however speculative, as long as it is not dressed as a finding. This rule exists because a "
    "panel split on it: the same reminder-open-rate link was correctly REFUSED when asserted as "
    "the cause, and should be SERVED when offered as somewhere to look.\n\n"
    "You are one of three independent reviewers and you will not see the others, or the "
    "system's own verdict. Judge it yourself.")

_USER = ("QUESTION ASKED:\n  {question}\n\n"
         "WHAT A CORRECT ANSWER NEEDS TO DO:\n  {expectation}\n\n"
         "THE ANSWER GIVEN:\n  {answer}\n\n"
         "THE GOVERNED FIGURES BEHIND IT:\n  {figures}")

_REPORT = {
    "name": "report_label",
    "description": "Report whether this answer should have been served.",
    "input_schema": {"type": "object", "properties": {
        "serve": {"type": "boolean",
                  "description": "true if it should have been served, false if refused"},
        "reason": {"type": "string", "description": "one sentence, concrete"}},
        "required": ["serve", "reason"]}}


def prose_decisions(paths: list[str], cases: dict) -> list[dict]:
    """Judged rows the gold-based scorer cannot settle: an answerable question whose answer is
    prose. Deduplicated on (question, verdict, answer) so three reps of the same text are one
    labelling job."""
    seen, out = set(), []
    for p in paths:
        for line in Path(p).open():
            r = json.loads(line)
            v = r.get("verifier_verdict")
            if not v or v.get("answers_question") is None or r.get("expected_refuse"):
                continue
            if r.get("gold") is not None and r.get("declared_value") is not None:
                continue                                  # the gold scorer has this one
            text = " ".join(((r.get("answer") or "") + " " + (r.get("explanation") or "")).split())
            key = (r["qid"], v["answers_question"], text[:160])
            if key in seen or not text:
                continue
            seen.add(key)
            expect = cases[r["qid"]]["expect"]
            want = (f"name the driver: {', '.join(expect.get('driver', [])[:4])}"
                    if expect["type"] == "diagnostic"
                    else f"mention: {', '.join(expect.get('keywords', [])[:5])}")
            out.append({"qid": r["qid"], "question": r["question"], "expectation": want,
                        "answer": text, "judge_passed": bool(v["answers_question"]),
                        "figures": ", ".join(
                            f"{s.get('tool')}={s.get('result_values')}"
                            for s in (r.get("steps") or []) if s.get("result_values"))[:400]})
    return out


def label(model, case: dict, lens: str) -> dict:
    turn = model.respond(
        Conversation.opening(_SYSTEM.format(lens=_LENS[lens]), _USER.format(**case)),
        [_REPORT], force_tool="report_label", temperature=0)
    for call in turn.tool_calls:
        if call.name == "report_label":
            return {"serve": bool(call.args.get("serve")), "reason": call.args.get("reason", "")}
    return {"serve": None, "reason": "no verdict"}


def main() -> None:
    import glob

    from agent.runtime.providers import get_model

    cases = {}
    for p in glob.glob("evals/cases/*/*.yml"):
        d = yaml.safe_load(open(p))
        for c in (d if isinstance(d, list) else d.get("cases") or []):
            cases[c["id"]] = c

    paths = sys.argv[2:] or ["runs/latest/raw.jsonl"]
    decisions = prose_decisions(paths, cases)
    model = get_model("gpt-5.6-terra")     # the panel is the instrument; do not economise on it
    print(f"labelling {len(decisions)} prose decisions with three independent lenses\n")

    labelled, escalations = [], []
    for c in decisions:
        votes = {lens: label(model, c, lens) for lens in _LENS}
        serve = [v["serve"] for v in votes.values()]
        agreed = len(set(serve)) == 1
        panel = serve[0] if agreed else None
        rec = {**{k: c[k] for k in ("qid", "question", "answer", "judge_passed")},
               "panel_says_serve": panel, "unanimous": agreed,
               "votes": {k: v for k, v in votes.items()}}
        labelled.append(rec)
        mark = "  " if agreed else "!!"
        agree_judge = "" if panel is None else (" agrees" if panel == c["judge_passed"]
                                                else "  <- DISAGREES WITH THE JUDGE")
        print(f"{mark} {c['qid']:24} judge={'serve' if c['judge_passed'] else 'refuse':6} "
              f"panel={'split' if panel is None else ('serve' if panel else 'refuse'):6}{agree_judge}")
        if not agreed:
            escalations.append(rec)

    settled = [r for r in labelled if r["unanimous"]]
    fp = sum(1 for r in settled if r["panel_says_serve"] and not r["judge_passed"])
    miss = sum(1 for r in settled if not r["panel_says_serve"] and r["judge_passed"])
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    from agent.guardrails.judge import prompt_fingerprint
    OUT.write_text(json.dumps({
        "method": "3 independent lenses (strict/pragmatic/skeptical), blind, unanimous-only; "
                  "splits escalated to a human rather than resolved by majority",
        "panel_model": "gpt-5.6-terra", "prompt_fingerprint": prompt_fingerprint(),
        "source_runs": paths, "n_decisions": len(labelled), "n_settled": len(settled),
        "n_escalated": len(escalations), "false_flag": fp, "miss": miss,
        "decisions": labelled}, indent=2))
    if escalations:
        ESCALATIONS.write_text(yaml.safe_dump(escalations, sort_keys=False, allow_unicode=True))

    print(f"\n  {len(settled)}/{len(labelled)} unanimous · {len(escalations)} escalated")
    if settled:
        print(f"  on the settled ones: judge false-flagged {fp}, missed {miss}")
    print(f"\nwrote {OUT}")
    if escalations:
        print(f"ESCALATED — {len(escalations)} genuinely arguable, needs a human: {ESCALATIONS}")


if __name__ == "__main__":
    main()
