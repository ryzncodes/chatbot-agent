"""Baseline rule-based planner implementation."""

from __future__ import annotations

from backend.planner.base import Planner
from backend.planner.types import Intent, PlannerAction, PlannerContext, PlannerDecision

PRODUCT_KEYWORDS = {
    "tumbler",
    "flask",
    "mug",
    "cup",
    "bottle",
    "merch",
    "thermos",
}

PRODUCT_KEYWORD_ALIASES = {
    "tumblers": "tumbler",
    "tumblrs": "tumbler",
    "cups": "cup",
    "mugs": "mug",
    "bottles": "bottle",
    "thermoses": "thermos",
}

LOCATION_ALIASES = {
    "ss2": "SS 2",
    "pj": "Petaling Jaya",
    "petaling": "Petaling Jaya",
    "kl": "Kuala Lumpur",
    "kuala lumpur": "Kuala Lumpur",
    "damansara": "Damansara",
}


class RuleBasedPlanner(Planner):
    """Lightweight intent classifier with deterministic slot requirements."""

    def describe(self) -> str:
        return "Rule-based keyword planner"

    def decide(self, context: PlannerContext) -> PlannerDecision:
        message = context.turn.content.lower()
        intent = self._classify_intent(message)
        intent = self._contextual_intent(intent, message, context)
        slot_updates = self._extract_slot_updates(intent, context, message)
        required_slots = self._derive_slots(intent, context)

        # If planner just extracted a slot, treat it as satisfied locally.
        for slot in slot_updates:
            if slot in required_slots:
                required_slots[slot] = True

        action = self._select_action(intent, required_slots)
        confidence = 0.65 if intent is Intent.UNKNOWN else 0.9

        return PlannerDecision(
            intent=intent,
            action=action,
            confidence=confidence,
            required_slots=required_slots,
            slot_updates=slot_updates,
        )

    def _classify_intent(self, message: str) -> Intent:
        if any(keyword in message for keyword in ["calc", "sum", "add", "minus", "+", "-"]):
            return Intent.CALCULATE
        if any(
            keyword in message
            for keyword in [
                "product",
                "drink",
                "tumbler",
                "tumblers",
                "merch",
                "mug",
                "mugs",
                "cup",
                "cups",
                "bottle",
                "bottles",
                "thermos",
            ]
        ):
            return Intent.PRODUCT_INFO
        if any(keyword in message for keyword in ["outlet", "store", "open", "closing", "hours"]):
            return Intent.OUTLET_INFO
        if "reset" in message:
            return Intent.RESET
        if any(keyword in message for keyword in ["hello", "hi", "thanks", "help"]):
            return Intent.SMALL_TALK
        return Intent.UNKNOWN

    def _derive_slots(self, intent: Intent, context: PlannerContext) -> dict[str, bool]:
        slots_required: dict[str, bool] = {}

        if intent is Intent.CALCULATE:
            slots_required["operation"] = "operation" in context.conversation.slots
        if intent is Intent.PRODUCT_INFO:
            slots_required["product_type"] = "product_type" in context.conversation.slots
        if intent is Intent.OUTLET_INFO:
            slots_required["location"] = "location" in context.conversation.slots

        return slots_required

    def _extract_slot_updates(
        self,
        intent: Intent,
        context: PlannerContext,
        message: str,
    ) -> dict[str, str]:
        tokens = [token.strip(" ,.!?;:\"'()") for token in message.split()]
        updates: dict[str, str] = {}

        if intent is Intent.CALCULATE:
            updates["operation"] = context.turn.content.strip()

        if intent is Intent.PRODUCT_INFO:
            for token in tokens:
                if not token:
                    continue
                canonical = None
                if token in PRODUCT_KEYWORDS:
                    canonical = token
                elif token in PRODUCT_KEYWORD_ALIASES:
                    canonical = PRODUCT_KEYWORD_ALIASES[token]
                else:
                    stripped = token.rstrip("s")
                    if stripped in PRODUCT_KEYWORDS:
                        canonical = stripped
                if canonical:
                    updates["product_type"] = canonical
                    break

        if intent is Intent.OUTLET_INFO:
            for alias, location in LOCATION_ALIASES.items():
                if alias in message:
                    updates["location"] = location
                    break

        return updates

    def _contextual_intent(self, intent: Intent, message: str, context: PlannerContext) -> Intent:
        if intent is not Intent.UNKNOWN:
            return intent

        follow_up_phrases = [
            "what else",
            "anything else",
            "another",
            "more option",
            "show me more",
            "something else",
        ]
        if context.conversation.slots.get("product_type"):
            if any(phrase in message for phrase in follow_up_phrases):
                return Intent.PRODUCT_INFO

        if context.conversation.slots.get("location"):
            if any(phrase in message for phrase in follow_up_phrases):
                return Intent.OUTLET_INFO

        return intent

    def _select_action(self, intent: Intent, slots: dict[str, bool]) -> PlannerAction:
        if intent is Intent.CALCULATE and slots.get("operation", False):
            return PlannerAction.CALL_CALCULATOR
        if intent is Intent.PRODUCT_INFO and slots.get("product_type", False):
            return PlannerAction.CALL_PRODUCTS
        if intent is Intent.OUTLET_INFO and slots.get("location", False):
            return PlannerAction.CALL_OUTLETS
        if intent is Intent.RESET:
            return PlannerAction.FINISH
        if intent in {Intent.UNKNOWN, Intent.SMALL_TALK}:
            return PlannerAction.FALLBACK
        return PlannerAction.ASK_FOLLOW_UP
