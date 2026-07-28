from datahub_memory.agent import route


def test_route():
    assert route("rich") == "answer_from_memory"
    assert route("sparse") == "answer_from_memory"
    assert route("gap") == "investigate"
