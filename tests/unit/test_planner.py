from backend.memory.models import ConversationSnapshot, MessageTurn
from backend.planner.simple import RuleBasedPlanner
from backend.planner.types import PlannerContext


def snapshot(slots=None):
    return ConversationSnapshot(
        conversation_id="conv-1",
        turns=[],
        slots=slots or {},
    )


def test_planner_extracts_product_slot_when_missing():
    planner = RuleBasedPlanner()
    turn = MessageTurn(conversation_id="conv-1", role="user", content="Do you have a stainless tumbler?")
    context = PlannerContext(turn=turn, conversation=snapshot())
    decision = planner.decide(context)

    assert decision.intent.value == "product_info"
    assert decision.slot_updates.get("product_type") == "tumbler"
    assert decision.required_slots.get("product_type") is True


def test_planner_respects_existing_product_slot():
    planner = RuleBasedPlanner()
    turn = MessageTurn(conversation_id="conv-1", role="user", content="Show me more options please")
    context = PlannerContext(turn=turn, conversation=snapshot({"product_type": "tumbler"}))
    decision = planner.decide(context)

    assert decision.intent.value == "product_info"
    assert decision.action.value == "call_products"
    assert not decision.slot_updates
    assert decision.required_slots.get("product_type") is True


def test_planner_extracts_operation_for_calculator():
    planner = RuleBasedPlanner()
    turn = MessageTurn(conversation_id="conv-1", role="user", content="calc 5 * 7")
    context = PlannerContext(turn=turn, conversation=snapshot())
    decision = planner.decide(context)

    assert decision.intent.value == "calculate"
    assert decision.action.value == "call_calculator"
    assert decision.slot_updates.get("operation") == "calc 5 * 7"


def test_planner_missing_location_requests_follow_up():
    planner = RuleBasedPlanner()
    turn = MessageTurn(conversation_id="conv-1", role="user", content="What are the opening hours?")
    context = PlannerContext(turn=turn, conversation=snapshot())
    decision = planner.decide(context)

    assert decision.intent.value == "outlet_info"
    assert decision.action.value == "ask_follow_up"
