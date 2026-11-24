"""M0 stub (replaced in M1 by FINAL/reference/impl/ebrain/store.py)."""
DEFAULTS: dict = {}


class EBrainError(Exception):
    pass


class UnknownTarget(EBrainError):
    pass


def _trigram_cosine(a, b):
    raise NotImplementedError("M1")


class Store:
    def __init__(self, path, config=None, user_id="local"):
        raise NotImplementedError("M1")
