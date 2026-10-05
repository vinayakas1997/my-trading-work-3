"""A model that writes multi-line code inside a JSON string puts raw newlines in it. Strict parsing rejected the whole
reply ("Invalid control character"), which burned LLM retries in the first real research batch. The content must come
through unchanged."""

from vinu_infra.llm.client import _parse_json_content as sync_parse
from vinu_infra.llm.client_async import _parse_json_content as async_parse

RAW = '{"code": "class A:\n\tdef f(self):\n\t\treturn 1", "n": 2}'


def test_raw_newlines_and_tabs_inside_a_string_are_accepted_unchanged():
    for parse in (sync_parse, async_parse):
        out = parse(RAW)
        assert out["code"] == "class A:\n\tdef f(self):\n\t\treturn 1" and out["n"] == 2


def test_fenced_replies_still_work():
    assert sync_parse("```json\n" + RAW + "\n```")["n"] == 2
