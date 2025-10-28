"""Planner abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .types import PlannerContext, PlannerDecision


class Planner(ABC):
    """Decides the next action given the latest conversational turn."""

    @abstractmethod
    def decide(self, context: PlannerContext) -> PlannerDecision:
        """Return the planner decision for a given context."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable summary of planner strategy."""
