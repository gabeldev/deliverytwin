"""G4: QLoRA SFT of Qwen3-1.7B on expert investigation traces (ADR-0007).

- 4-bit NF4 base, LoRA r=16 on attention+MLP projections, gradient checkpointing, no fp32
  upcast (memory gate), loss only on assistant tokens (the full vocabulary logits are only
  computed at target positions).
- Replay: a fraction of steps uses general instruction data (Dolly-15k, CC BY-SA 3.0) to
  limit catastrophic forgetting.
- General-capability check: assistant-token NLL on held-out Dolly examples, before and
  after training.

Usage: uv run --group train python scripts/g4_train.py [--epochs 2] [--replay 0.2]
Outputs: runs/g4/adapter/ (git-ignored), docs/reports/G4_TRAIN.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from deliverytwin.training.chat import tokenize_with_mask

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen3-1.7B"
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text().splitlines() if line]


def dolly(tok, n_train: int, n_eval: int, seed: int = 0, max_len: int = 1024):
    path = hf_hub_download("databricks/databricks-dolly-15k", "databricks-dolly-15k.jsonl",
                           repo_type="dataset")
    rows = load_jsonl(Path(path))
    random.Random(seed).shuffle(rows)
    out = []
    for r in rows:
        user = r["instruction"] + (f"\n\nContext:\n{r['context']}" if r.get("context") else "")
        msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": r["response"]}]
        ids, mask = tokenize_with_mask(tok, msgs, [])
        if 0 < sum(mask) and len(ids) <= max_len:
            out.append({"input_ids": ids, "mask": mask})
        if len(out) >= n_train + n_eval:
            break
    return out[:n_train], out[n_train:n_train + n_eval]


def target_loss(model, ids: list[int], mask: list[int]) -> torch.Tensor:
    """Mean NLL of assistant tokens: position t predicts token t+1 where mask[t+1] == 1."""
    x = torch.tensor([ids], device="cuda")
    pos = torch.tensor([t for t in range(len(ids) - 1) if mask[t + 1]], device="cuda")
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    hidden = base.model(input_ids=x).last_hidden_state[0]
    logits = base.lm_head(hidden[pos]).float()
    return torch.nn.functional.cross_entropy(logits, x[0, pos + 1])


@torch.no_grad()
def mean_loss(model, rows: list[dict]) -> float:
    model.eval()
    losses = [float(target_loss(model, r["input_ids"], r["mask"])) for r in rows]
    model.train()
    return sum(losses) / len(losses)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--replay", type=float, default=0.2)
    ap.add_argument("--max-train", type=int, default=0, help="0 = all")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    random.seed(a.seed)
    g4 = ROOT / "runs" / "g4"
    train = load_jsonl(g4 / "sft_train.jsonl")
    val = load_jsonl(g4 / "sft_val.jsonl")
    if a.max_train:
        train = train[:a.max_train]
    tok = AutoTokenizer.from_pretrained(MODEL)
    n_replay = int(len(train) * a.replay / max(1e-9, 1 - a.replay))
    dolly_train, dolly_eval = dolly(tok, n_replay, 150)

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb,
                                                 device_map={"": 0}, dtype=torch.bfloat16)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                                             target_modules=TARGETS, task_type="CAUSAL_LM"))
    model.train()

    report = {"model": MODEL, "train_traces": len(train), "val_traces": len(val),
              "replay_examples": len(dolly_train), "general_eval_examples": len(dolly_eval),
              "epochs": a.epochs, "lr": a.lr, "grad_accum": a.accum, "lora_r": 16, "seed": a.seed}
    t0 = time.time()
    report["before"] = {"val_loss": round(mean_loss(model, val), 4),
                        "general_loss": round(mean_loss(model, dolly_eval), 4)}
    print("before", report["before"], flush=True)

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr,
                            weight_decay=0.0)
    data = [("trace", r) for r in train] + [("general", r) for r in dolly_train]
    total_steps = math.ceil(len(data) * a.epochs / a.accum)
    warm = max(1, int(0.05 * total_steps))

    def lr_at(step):
        if step < warm:
            return a.lr * (step + 1) / warm
        frac = (step - warm) / max(1, total_steps - warm)
        return a.lr * 0.5 * (1 + math.cos(math.pi * frac))

    log = (g4 / "train_log.jsonl").open("w")
    step, micro, running = 0, 0, []
    report["epochs_log"] = []
    for ep in range(a.epochs):
        random.Random(a.seed + ep).shuffle(data)
        for kind, r in data:
            loss = target_loss(model, r["input_ids"], r["mask"]) / a.accum
            loss.backward()
            running.append((kind, float(loss) * a.accum))
            micro += 1
            if micro % a.accum == 0:
                for gparam in opt.param_groups:
                    gparam["lr"] = lr_at(step)
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                tr = [v for k, v in running if k == "trace"]
                log.write(json.dumps({"step": step, "lr": lr_at(step - 1),
                                      "trace_loss": sum(tr) / max(1, len(tr)),
                                      "mem_gb": torch.cuda.max_memory_allocated() / 2**30,
                                      "elapsed_s": time.time() - t0}) + "\n")
                log.flush()
                running = []
                if step % 20 == 0:
                    print(f"step {step}/{total_steps} trace_loss {sum(tr) / max(1, len(tr)):.4f}",
                          flush=True)
        vl = mean_loss(model, val)
        report["epochs_log"].append({"epoch": ep + 1, "val_loss": round(vl, 4)})
        print(f"epoch {ep + 1} val_loss {vl:.4f}", flush=True)
    rest = micro % a.accum
    if rest:  # flush the last partial accumulation batch (Codex review G4/G5 #3)
        params = [p for p in model.parameters() if p.requires_grad]
        for p in params:
            if p.grad is not None:
                p.grad.mul_(a.accum / rest)  # losses were divided by accum, not by rest
        for gparam in opt.param_groups:
            gparam["lr"] = lr_at(min(step, total_steps - 1))
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        step += 1
    report["after"] = {"val_loss": round(mean_loss(model, val), 4),
                       "general_loss": round(mean_loss(model, dolly_eval), 4)}
    report["steps"] = step
    report["minutes"] = round((time.time() - t0) / 60, 1)
    report["peak_mem_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 3)
    model.save_pretrained(str(g4 / "adapter"))
    (ROOT / "docs" / "reports" / "G4_TRAIN.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
