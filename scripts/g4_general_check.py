"""G4: independent general-capability check, base vs SFT (catastrophic forgetting).

The Dolly replay loss reported by g4_train.py is not independent (replay comes from the
same distribution). This script measures exact-match accuracy on a fixed GSM8K test subset
(MIT licence), a different task and distribution, with the same non-thinking rendering
used everywhere in G4 and greedy decoding. Base and SFT are scored on the same problems,
so the comparison is paired (exact McNemar).

Usage: uv run --group train python scripts/g4_general_check.py --n 150
Output: docs/reports/G4_GENERAL_CHECK.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
import urllib.request
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen3-1.7B"
GSM8K_URL = ("https://raw.githubusercontent.com/openai/grade-school-math/master/"
             "grade_school_math/data/test.jsonl")
PROMPT = ("Solve the problem. Reason briefly step by step, then give the final answer on "
          "the last line as: Answer: <number>\n\n{q}")


def gold(answer: str) -> str:
    return norm(answer.split("####")[-1])


def norm(x: str) -> str:
    x = x.strip().replace(",", "").replace("$", "").rstrip(".")
    try:
        f = float(x)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return x


_FINAL = re.compile(r"^(-?\d+(?:\.\d+)?)(?:\s+[A-Za-z].*)?$")


def predicted(text: str) -> str | None:
    """Value on the LAST 'Answer:' line, or None (scored wrong). No fallback to incidental
    numbers; '-$12' keeps its sign; '1e3' or '12/5' are rejected (Codex review G4/G5 #2)."""
    lines = [ln for ln in text.splitlines() if "Answer:" in ln]
    if not lines:
        return None
    raw = lines[-1].split("Answer:", 1)[1].strip().rstrip(".")
    raw = raw.replace("$", "").replace(",", "").replace("**", "").strip()
    m = _FINAL.match(raw)
    return norm(m.group(1)) if m else None


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def load_problems(n: int, seed: int = 0) -> list[dict]:
    cache = ROOT / "runs" / "g4" / "gsm8k_test.jsonl"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(GSM8K_URL, timeout=60) as r:
            cache.write_bytes(r.read())
    rows = [json.loads(line) for line in cache.read_text().splitlines() if line]
    random.Random(seed).shuffle(rows)
    return rows[:n]


def run(adapter: str | None, problems: list[dict], max_new: int) -> list[dict]:
    import torch

    from deliverytwin.agent.local_llm import LocalQwenClient
    from deliverytwin.training.chat import render
    c = LocalQwenClient(MODEL, adapter=adapter, max_new_tokens=max_new)
    out = []
    for p in problems:
        text = render(c.tok, [{"role": "user", "content": PROMPT.format(q=p["question"])}], [],
                      generation_prompt=True)
        ids = c.tok(text, add_special_tokens=False, return_tensors="pt")["input_ids"].to("cuda")
        with torch.no_grad():
            g = c.m.generate(input_ids=ids, max_new_tokens=max_new, do_sample=False,
                             eos_token_id=c.end_id, pad_token_id=c.tok.eos_token_id)
        ans = c.tok.decode(g[0, ids.shape[1]:], skip_special_tokens=True)
        pred = predicted(ans)
        out.append({"pred": pred, "gold": gold(p["answer"]), "ok": pred == gold(p["answer"]),
                    "response": ans})
    del c
    torch.cuda.empty_cache()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--max-new", type=int, default=512)
    ap.add_argument("--adapter", default=str(ROOT / "runs" / "g4" / "adapter"))
    a = ap.parse_args()
    problems = load_problems(a.n)
    t0 = time.time()
    base = run(None, problems, a.max_new)
    sft = run(a.adapter, problems, a.max_new)
    b = sum(x["ok"] and not y["ok"] for x, y in zip(base, sft, strict=True))
    c = sum(y["ok"] and not x["ok"] for x, y in zip(base, sft, strict=True))
    rep = {"benchmark": "GSM8K test (openai/grade-school-math, MIT), fixed random subset, seed 0",
           "n": a.n, "decoding": f"greedy, non-thinking, max_new_tokens={a.max_new}",
           "base_acc": round(sum(x["ok"] for x in base) / a.n, 4),
           "sft_acc": round(sum(y["ok"] for y in sft) / a.n, 4),
           "base_only_correct": b, "sft_only_correct": c,
           "mcnemar_p": round(mcnemar_exact(b, c), 4),
           "minutes": round((time.time() - t0) / 60, 1)}
    rep["no_parsable_answer"] = {"base": sum(x["pred"] is None for x in base),
                                 "sft": sum(y["pred"] is None for y in sft)}
    (ROOT / "docs" / "reports" / "G4_GENERAL_CHECK.json").write_text(json.dumps(rep, indent=2))
    out = ROOT / "runs" / "g4" / "gsm8k_responses.json"
    out.write_text(json.dumps({"base": base, "sft": sft}, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
