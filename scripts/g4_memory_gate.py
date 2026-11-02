"""G4 memory gate (ADR-0007): does QLoRA training fit the local 6 GB GPU?

For each model and sequence length, load the model in 4-bit NF4, attach LoRA adapters
(attention + MLP projections), enable gradient checkpointing, and run one full training
step (forward + backward + optimizer) on a batch of 1. Records peak allocated/reserved
VRAM or the OOM. Writes docs/reports/G4_MEMORY_GATE.json.

Usage: uv run --group train python scripts/g4_memory_gate.py [--models Qwen/Qwen3-1.7B]
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def selected_loss(model, ids, mask_frac: float):
    """Causal-LM loss computed only on a fraction of positions (as in completion-only SFT):
    run the decoder, then apply the LM head only where labels exist, so the full
    (seq_len x 152k vocab) logits tensor is never materialised."""
    base = model.get_base_model()
    hidden = base.model(input_ids=ids).last_hidden_state  # (1, L, d)
    L = ids.shape[1]
    k = max(1, int(L * mask_frac))
    pos = torch.arange(L - k - 1, L - 1, device=ids.device)  # last k positions predict next
    logits = base.lm_head(hidden[0, pos]).float()
    return torch.nn.functional.cross_entropy(logits, ids[0, pos + 1])


def step(model_id: str, seq_len: int, mask_frac: float = 0.3) -> dict:
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    t = time.time()
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=bnb,
                                                 device_map={"": 0}, dtype=torch.bfloat16)
    # No fp32 upcast of embeddings/norms (prepare_model_for_kbit_training does that and
    # costs ~1.2 GB here); gradient checkpointing with inputs requiring grad instead.
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                                             target_modules=TARGETS, task_type="CAUSAL_LM"))
    model.train()  # gradient checkpointing only applies in training mode
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
    ids = torch.randint(100, 30000, (1, seq_len), device="cuda")
    out = {"model": model_id, "seq_len": seq_len, "trainable_params": trainable,
           "loss_positions_frac": mask_frac, "fp32_upcast": False}
    try:
        loss = selected_loss(model, ids, mask_frac)
        loss.backward()
        opt.step()
        opt.zero_grad()
        torch.cuda.synchronize()
        out.update(ok=True, loss=round(float(loss), 3))
    except torch.OutOfMemoryError:
        out.update(ok=False, error="OOM")
    out.update(peak_allocated_gb=round(torch.cuda.max_memory_allocated() / 2**30, 3),
               peak_reserved_gb=round(torch.cuda.max_memory_reserved() / 2**30, 3),
               seconds=round(time.time() - t, 1))
    del model, opt
    gc.collect()
    torch.cuda.empty_cache()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--lens", default="1024,2048,4096")
    a = ap.parse_args()
    total = torch.cuda.get_device_properties(0).total_memory / 2**30
    results = []
    for m in a.models.split(","):
        for L in (int(x) for x in a.lens.split(",")):
            r = step(m, L)
            print(json.dumps(r))
            results.append(r)
            if not r["ok"]:
                break
    out = {"gpu": torch.cuda.get_device_name(0), "total_gb": round(total, 2),
           "torch": torch.__version__, "results": results}
    (ROOT / "docs" / "reports" / "G4_MEMORY_GATE.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
