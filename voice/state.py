"""Explicit session transitions; invalid transitions are visible defects."""
from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    ERROR = "ERROR"


class Machine:
    def __init__(self) -> None:
        self.state = State.IDLE
        self.epoch = 0

    def transition(self, next_state: State) -> None:
        allowed = {
            State.IDLE: {State.ARMED},
            State.ARMED: {State.LISTENING, State.ERROR, State.IDLE},
            State.LISTENING: {State.THINKING, State.ERROR, State.IDLE},
            State.THINKING: {
                State.SPEAKING, State.LISTENING, State.INTERRUPTED,
                State.ERROR, State.IDLE,
            },
            State.SPEAKING: {
                State.LISTENING, State.INTERRUPTED, State.ERROR, State.IDLE,
            },
            State.INTERRUPTED: {State.LISTENING, State.ERROR, State.IDLE},
            State.ERROR: {State.IDLE},
        }
        if next_state == self.state:
            return
        if next_state not in allowed[self.state]:
            raise ValueError(f"Invalid transition {self.state}:{next_state}")
        self.state = next_state
        if next_state in {State.IDLE, State.INTERRUPTED}:
            self.epoch += 1
