from backend.memory.models import MessageTurn


def test_append_and_fetch(memory_store):
    turn = MessageTurn(conversation_id="conv-1", role="user", content="Hello")
    memory_store.append_turn(turn)

    turns = memory_store.fetch_recent_turns("conv-1", limit=5)

    assert len(turns) == 1
    assert turns[0].content == "Hello"
