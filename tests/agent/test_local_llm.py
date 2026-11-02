"""G4: tool-call parsing and the shared train/inference chat rendering."""

import json

import pytest

from deliverytwin.agent.llm_agent import TOOLS, compact_tools
from deliverytwin.agent.local_llm import parse_tool_calls
from deliverytwin.training.chat import ASSISTANT, THINK, _normalise, assistant_char_spans


def test_parse_single_and_multiple_tool_calls():
    text = ('Checking.\n<tool_call>\n{"name": "query_orders", "arguments": {"group_by": "zone"}}\n'
            '</tool_call>\n<tool_call>\n{"name": "submit", "arguments": {"cause": null, '
            '"confidence": 0.2}}\n</tool_call>')
    content, calls = parse_tool_calls(text)
    assert content == "Checking."
    assert [c.function.name for c in calls] == ["query_orders", "submit"]
    assert json.loads(calls[0].function.arguments) == {"group_by": "zone"}
    assert calls[1].model_dump()["function"]["name"] == "submit"


def test_malformed_tool_call_is_reported_not_raised():
    _, calls = parse_tool_calls("<tool_call>{not json}</tool_call>")
    assert calls[0].function.name == "__malformed__"


def test_plain_text_has_no_calls():
    content, calls = parse_tool_calls("I think the cause is unclear.")
    assert calls == [] and content.startswith("I think")


def test_every_assistant_turn_gets_one_empty_think_block():
    raw = f"x{ASSISTANT}{THINK}a<|im_end|>{ASSISTANT}b<|im_end|>{ASSISTANT}"
    norm = _normalise(raw)
    assert norm.count(ASSISTANT + THINK) == 3 and THINK + THINK not in norm
    spans = assistant_char_spans(norm)
    assert [norm[a:b] for a, b in spans][:2] == ["a<|im_end|>", "b<|im_end|>"]


def test_compact_tools_keep_names_fields_and_enums():
    full = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}
    compact = {t["function"]["name"]: t["function"]["parameters"] for t in compact_tools()}
    assert set(full) == set(compact)
    for name in full:
        assert set(full[name]["properties"]) == set(compact[name]["properties"])
    assert "description" not in json.dumps(compact)


def test_mask_covers_only_assistant_text():
    tf = pytest.importorskip("transformers")
    from deliverytwin.training.chat import tokenize_with_mask
    try:
        tok = tf.AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B", local_files_only=True)
    except OSError:
        pytest.skip("tokenizer not cached locally")
    msgs = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USERTEXT"},
            {"role": "assistant", "content": "ANSWERTEXT"}]
    ids, mask = tokenize_with_mask(tok, msgs, [])
    target = tok.decode([t for t, m in zip(ids, mask, strict=True) if m])
    assert "ANSWERTEXT" in target and "USERTEXT" not in target and "SYS" not in target
