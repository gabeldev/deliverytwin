"""Build the G4 SFT dataset from expert traces (development seed only).

- Instances: development master seed 2026; split by the instance's private split
  (train -> training set, dev -> validation). The final evaluation seed 515151 is never
  touched here.
- Each trace is rendered with the Qwen3 chat template (tools included, thinking off) and
  an assistant-only loss mask is derived by prefix differences.
- Traces longer than --max-len tokens (the memory gate limit) are dropped and counted.

Usage: uv run --group train python scripts/g4_build_dataset.py --per-level 300
Output: runs/g4/sft_{train,val}.jsonl (git-ignored) + docs/reports/G4_DATASET_STATS.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from transformers import AutoTokenizer

from deliverytwin.agent.llm_agent import compact_tools
from deliverytwin.benchmark.generator import generate_instance
from deliverytwin.training.chat import to_qwen, tokenize_with_mask
from deliverytwin.training.traces import expert_episode, keep

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen3-1.7B"
TOOLS = compact_tools()
DEV_SEED = 2026


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=300)
    ap.add_argument("--max-len", type=int, default=4608)  # = recorded G4 dataset
    a = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(MODEL)
    out_dir = ROOT / "runs" / "g4"
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    lengths = {"train": [], "val": []}
    files = {"train": (out_dir / "sft_train.jsonl").open("w"),
             "val": (out_dir / "sft_val.jsonl").open("w")}
    for level in ("L0", "L1", "L2"):
        for i in range(a.per_level):
            inst = generate_instance(level, i, master_seed=DEV_SEED)
            split = {"train": "train", "dev": "val"}.get(inst.private.split)
            if split is None:  # "test" split of the dev seed: unused
                stats["skipped_test_split"] += 1
                continue
            trace, session = expert_episode(inst)
            if not keep(inst, session):
                stats[f"rejected_incorrect_{level}"] += 1
                continue
            msgs = to_qwen(trace.messages)
            ids, mask = tokenize_with_mask(tok, msgs, TOOLS)
            if len(ids) > a.max_len:
                stats[f"dropped_too_long_{level}"] += 1
                continue
            files[split].write(json.dumps({"level": level, "family": inst.private.family,
                                           "input_ids": ids, "mask": mask}) + "\n")
            stats[f"kept_{split}_{level}"] += 1
            lengths[split].append(len(ids))
    for f in files.values():
        f.close()
    summary = {"model": MODEL, "dev_seed": DEV_SEED, "max_len": a.max_len,
               "per_level_attempted": a.per_level, "counts": dict(sorted(stats.items())),
               "length": {k: {"n": len(v), "mean": round(sum(v) / len(v), 1) if v else None,
                              "max": max(v) if v else None} for k, v in lengths.items()}}
    (ROOT / "docs" / "reports" / "G4_DATASET_STATS.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
