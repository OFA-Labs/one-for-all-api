"""Measurement variant: reference Store with config overrides {"heal_mode": "auto", "subject_join": "on"}."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "..", "..", "impl")))
from ebrain.store import Store  # noqa: E402


class Adapter(Store):
    name = "ebrain-ref-join_on_heal_auto"

    def __init__(self, workdir, config=None):
        super().__init__(workdir, {**(config or {}), **{"heal_mode": "auto", "subject_join": "on"}}, user_id="local")
