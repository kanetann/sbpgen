from sbpgen import parse_line


def test_parse_line_double_slash_creates_branch_edges():
    line = (
        "Add to Cart:C Click Cart/F Add to Cart/"
        "B Update Inventory//P Check DB/B Reflect Remaining/P Log Record"
    )
    step, flow_seq, act_seq, edges = parse_line(line)

    assert step == "Add to Cart"
    assert flow_seq == ["C", "F", "B", "P", "B", "P"]
    assert act_seq == [
        "Click Cart",
        "Add to Cart",
        "Update Inventory",
        "Check DB",
        "Reflect Remaining",
        "Log Record",
    ]
    assert edges == [(0, 1), (1, 2), (2, 3), (2, 4), (3, 4), (4, 5)]


def test_parse_line_double_slash_requires_follow_up_segment():
    line = "Step:B Update//P Check"
    try:
        parse_line(line)
    except ValueError as exc:
        assert "Double slash" in str(exc)
    else:
        raise AssertionError("Expected ValueError for trailing double slash")


def test_pipe_separator_suppresses_edge():
    step, flow_seq, act_seq, edges = parse_line("Step:C First|F Second/F Third")

    assert flow_seq == ["C", "F", "F"]
    assert act_seq == ["First", "Second", "Third"]
    assert (0, 1) not in edges
    assert (1, 2) in edges
