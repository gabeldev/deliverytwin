"""Local Qwen3 client with the same interface as LLMClient (G4).

Uses the shared training/inference rendering (deliverytwin.training.chat) and the compact
tool schemas, greedy decoding (reproducible), and parses Qwen <tool_call> blocks into
OpenAI-style tool calls so `run_llm_agent` works unchanged. No network, no cost.
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

from deliverytwin.agent.llm_agent import compact_tools
from deliverytwin.training.chat import render, to_qwen

_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_tool_calls(text: str):
    calls = []
    for n, m in enumerate(_CALL.finditer(text), 1):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            obj = None
        # Only {"name": str, "arguments": object} is a call; anything else goes to the
        # malformed-call error path instead of crashing the agent loop (Codex G4/G5 #1).
        if (not isinstance(obj, dict) or not isinstance(obj.get("name"), str)
                or not isinstance(obj.get("arguments", {}), dict)):
            obj = {"name": "__malformed__", "arguments": {}}
        name = obj["name"]
        args = json.dumps(obj.get("arguments", {}))
        cid = f"call_{n}"
        calls.append(SimpleNamespace(
            id=cid, function=SimpleNamespace(name=name, arguments=args),
            model_dump=lambda cid=cid, name=name, args=args: {
                "id": cid, "type": "function", "function": {"name": name, "arguments": args}}))
    content = _CALL.split(text)[0].strip() if calls else text.strip()
    return content, calls


class LocalQwenClient:
    def __init__(self, model_id: str = "Qwen/Qwen3-1.7B", adapter: str | None = None,
                 max_new_tokens: int = 512):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        self.torch = torch
        self.model = f"{model_id}{'+' + adapter if adapter else ''}"
        self.tok = AutoTokenizer.from_pretrained(model_id)
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_use_double_quant=True)
        m = AutoModelForCausalLM.from_pretrained(model_id, quantization_config=bnb,
                                                 device_map={"": 0}, dtype=torch.bfloat16)
        if adapter:
            from peft import PeftModel
            m = PeftModel.from_pretrained(m, adapter)
        m.eval()
        self.m = m
        self.tools = compact_tools()
        self.max_new_tokens = max_new_tokens
        self.end_id = self.tok.convert_tokens_to_ids("<|im_end|>")
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def chat(self, messages: list[dict], tools=None):
        # Default schema = the one used in training; a reduced list (ablations) is compacted
        # the same way.
        schema = self.tools if tools is None or len(tools) == len(self.tools) else compact_tools(tools)
        text = render(self.tok, to_qwen(messages), schema, generation_prompt=True)
        ids = self.tok(text, add_special_tokens=False, return_tensors="pt")["input_ids"].to("cuda")
        with self.torch.no_grad():
            out = self.m.generate(input_ids=ids, max_new_tokens=self.max_new_tokens,
                                  do_sample=False, eos_token_id=self.end_id,
                                  pad_token_id=self.tok.eos_token_id)
        gen = out[0, ids.shape[1]:]
        self.prompt_tokens += ids.shape[1]
        self.completion_tokens += gen.shape[0]
        decoded = self.tok.decode(gen, skip_special_tokens=False).replace("<|im_end|>", "")
        content, calls = parse_tool_calls(decoded)
        msg = SimpleNamespace(content=content, tool_calls=calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
