"""One chat rendering for both training and inference (Qwen3, non-thinking mode).

The Qwen3 template inserts the empty reasoning block "<think>\\n\\n</think>\\n\\n" only in
the turn being generated and drops it from earlier assistant turns, so a conversation is
not prefix-stable. We render with the official template and then put the empty block in
EVERY assistant turn. Training targets and inference prompts therefore share exactly the
same format, and the base model is evaluated with the same rendering.
"""

from __future__ import annotations

import json

ASSISTANT = "<|im_start|>assistant\n"
THINK = "<think>\n\n</think>\n\n"
END = "<|im_end|>"


def to_qwen(messages: list[dict]) -> list[dict]:
    """OpenAI-style tool calls -> Qwen chat-template form (arguments as dicts)."""
    out = []
    for m in messages:
        m = dict(m)
        if m.get("tool_calls"):
            m["tool_calls"] = [{"type": "function", "function": {
                "name": c["function"]["name"],
                "arguments": (json.loads(c["function"]["arguments"])
                              if isinstance(c["function"]["arguments"], str)
                              else c["function"]["arguments"])}} for c in m["tool_calls"]]
            m.pop("id", None)
        if m["role"] == "tool":
            m = {"role": "tool", "content": m["content"]}
        out.append(m)
    return out


def _normalise(text: str) -> str:
    # Remove any template-inserted empty blocks, then add one to every assistant turn.
    text = text.replace(ASSISTANT + THINK, ASSISTANT)
    return text.replace(ASSISTANT, ASSISTANT + THINK)


def render(tok, messages: list[dict], tools: list[dict], generation_prompt: bool) -> str:
    text = tok.apply_chat_template(messages, tools=tools, tokenize=False,
                                   add_generation_prompt=generation_prompt,
                                   enable_thinking=False)
    return _normalise(text)


def assistant_char_spans(text: str) -> list[tuple[int, int]]:
    """[start, end) of each assistant target: after the think block, through <|im_end|>."""
    spans, i = [], 0
    while True:
        a = text.find(ASSISTANT + THINK, i)
        if a < 0:
            return spans
        start = a + len(ASSISTANT + THINK)
        e = text.find(END, start)
        if e < 0:
            spans.append((start, len(text)))
            return spans
        spans.append((start, e + len(END)))
        i = e


def tokenize_with_mask(tok, messages: list[dict], tools: list[dict]) -> tuple[list[int], list[int]]:
    text = render(tok, messages, tools, generation_prompt=False)
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    spans = assistant_char_spans(text)
    mask = []
    for s, e in enc["offset_mapping"]:
        mask.append(int(any(a <= s and e <= b for a, b in spans) and e > s))
    return enc["input_ids"], mask
