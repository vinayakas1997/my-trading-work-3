from vinu_agent.agent.loop import cap_tool_result


def test_a_huge_tool_result_is_cut_with_a_marker():
    out = cap_tool_result(name="get_cluster_angles", content="x" * 9_677_263)
    assert len(out) < 101_000 and "TRUNCATED" in out and "get_cluster_angles" in out and "9,677,263" in out


def test_a_normal_result_is_untouched():
    assert cap_tool_result(name="t", content='{"ok": true}') == '{"ok": true}'
    assert cap_tool_result(name="t", content=None) is None
