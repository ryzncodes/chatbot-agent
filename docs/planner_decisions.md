# Planner Decision Notes

This document summarizes the rule-based planner that orchestrates `/chat` responses.

## Overview

The planner processes each incoming turn and outputs:

- `intent`: high-level goal inferred from the user utterance.
- `action`: next step (call a tool, ask a follow-up, finish, fallback).
- `slot_updates`: slots captured during the turn for memory persistence.
- `required_slots`: slots still needed before safely calling a tool.

The planner uses keyword heuristics to keep the implementation deterministic and
easy to test while still supporting multi-turn flows.

## Intent Classification

| Intent | Trigger keywords | Examples |
| --- | --- | --- |
| `calculate` | `calc`, `sum`, `add`, math symbols (`+`, `-`, `*`, `/`) | “calc 5 * 7” |
| `product_info` | `product`, `drink`, `tumbler`, `merch`, `cup`, `bottle` | “Do you have stainless tumblers?” |
| `outlet_info` | `outlet`, `store`, `hours`, `opening`, `closing`, `service` | “What time does SS2 open?” |
| `reset` | `reset` | “Reset conversation” |
| `small_talk` | greetings and polite phrases (`hello`, `hi`, `thanks`, `help`) | “Thanks!” |
| `unknown` | fallback when no keywords match | “Blorp?” |

## Slot Extraction & Requirements

Slots are persisted in `ConversationSnapshot.slots` to maintain context across turns.

- `operation`: full user expression for calculator calls. Populated when intent is `calculate`.
- `product_type`: drinkware keyword (tumbler, mug, etc.) gathered when intent is `product_info`.
- `location`: inferred outlet location from aliases (e.g., `ss2` → `SS 2`, `pj` → `Petaling Jaya`).

Before calling a tool the planner ensures required slots are satisfied:

- `/calculator` requires `operation`.
- `/products` requires `product_type`.
- `/outlets` requires `location`.

If a required slot is missing, the action downgrades to `ask_follow_up` and the
assistant clarifies (“Could you share the location?”). When intent confidence is
low (<0.6) or the utterance is small talk, the planner emits `fallback` instead.

## Actions & Fallbacks

| Action | Conditions |
| --- | --- |
| `call_calculator` | Intent `calculate` **and** `operation` slot present. |
| `call_products` | Intent `product_info` **and** `product_type` slot present. |
| `call_outlets` | Intent `outlet_info` **and** `location` slot present. |
| `ask_follow_up` | Intent is tool-related but required slot missing. |
| `finish` | Intent `reset`; conversation state is cleared. |
| `fallback` | Intent `unknown` or `small_talk`; assistant guides user to clarify. |

When a tool raises an exception (network issue, bad payload, etc.) the controller
logs the failure and returns a safe recovery message (“I ran into an issue calling
that tool. Could you try again later?”) while keeping the conversation alive.

## Memory & Metrics

- Slot updates are saved via `SQLiteMemoryStore.upsert_slots` after each decision.
- Each decision records a timeline event (`intent`, `action`, success flag) for
  frontend visualization.
- Metrics (`total_requests`, intent/action counts) update per turn to support the
  `/metrics` endpoint.

## Future Enhancements

- Replace keyword classification with a lightweight intent model once available.
- Expand `LOCATION_ALIASES` using the scraped outlet dataset.
- Introduce confidence scores for tool outputs to drive richer fallback messaging.
