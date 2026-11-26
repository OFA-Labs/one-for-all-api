"""Vault, handles and the credential broker (§8). Values never leave this package except into a
verified target field via an injector; callers receive success/failure only."""
from .handles import Handle, HandleError, parse_handle
from .store import Vault, VaultLocked

__all__ = ["Handle", "HandleError", "parse_handle", "Vault", "VaultLocked"]
