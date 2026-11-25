"""Self-contained strict JSON-Schema subset validator (test-only).

The API venv intentionally has no ``jsonschema`` dependency. This module
implements the exact keyword subset used by the versioned schema-3 fixtures
under ``docs/ebrain/contracts/v3/``:

    type, required, additionalProperties, enum, const, items, properties,
    pattern, minLength, minimum, $ref (local ``#/definitions/...`` only)

An unknown keyword is a hard :class:`SchemaError` rather than a silently
ignored constraint, so a fixture cannot appear valid because its schema used
an unsupported keyword. ``type`` may be a string or a list of strings.
"""
from __future__ import annotations

import re
from typing import Any

SUPPORTED_KEYWORDS = frozenset({
    "type", "required", "additionalProperties", "enum", "const", "items",
    "properties", "pattern", "minLength", "minimum", "$ref", "definitions",
    "title", "description",
})

_TYPES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


class SchemaError(ValueError):
    """The schema itself is malformed or uses an unsupported keyword."""


class SchemaValidationError(ValueError):
    """An instance violates one or more schema constraints."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(errors))


def _is_type(value: Any, name: str) -> bool:
    cls = _TYPES[name]
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, cls)


class Validator:
    """Validate instances against one schema document."""

    def __init__(self, schema: dict[str, Any]) -> None:
        if not isinstance(schema, dict):
            raise SchemaError("schema root must be an object")
        self.root = schema
        self._check_schema(schema, "#")

    def _check_schema(self, schema: Any, path: str) -> None:
        if not isinstance(schema, dict):
            return
        unknown = sorted(set(schema) - SUPPORTED_KEYWORDS)
        if unknown:
            raise SchemaError(f"unsupported keyword(s) at {path}: {unknown}")
        typ = schema.get("type")
        if typ is not None:
            names = [typ] if isinstance(typ, str) else list(typ)
            if not all(isinstance(n, str) and n in _TYPES for n in names):
                raise SchemaError(f"invalid type at {path}: {typ!r}")
        if "properties" in schema:
            props = schema["properties"]
            if not isinstance(props, dict):
                raise SchemaError(f"properties must be an object at {path}")
            for key, sub in props.items():
                self._check_schema(sub, f"{path}/properties/{key}")
        if "items" in schema:
            self._check_schema(schema["items"], f"{path}/items")
        ap = schema.get("additionalProperties", True)
        if isinstance(ap, dict):
            self._check_schema(ap, f"{path}/additionalProperties")
        elif not isinstance(ap, bool):
            raise SchemaError(
                f"additionalProperties must be bool or schema at {path}")
        definitions = schema.get("definitions")
        if definitions is not None:
            if not isinstance(definitions, dict):
                raise SchemaError(f"definitions must be an object at {path}")
            for key, sub in definitions.items():
                self._check_schema(sub, f"{path}/definitions/{key}")

    def _resolve(self, ref: str) -> dict[str, Any]:
        if not ref.startswith("#/definitions/"):
            raise SchemaError(f"only local #/definitions/ refs are supported: {ref}")
        node: Any = self.root
        for part in ref[len("#/"):].split("/"):
            if not isinstance(node, dict) or part not in node:
                raise SchemaError(f"unresolved $ref {ref}")
            node = node[part]
        if not isinstance(node, dict):
            raise SchemaError(f"$ref {ref} does not point to a schema object")
        return node

    def validate(self, instance: Any) -> list[str]:
        """Return a sorted list of human-readable violations (empty = valid)."""
        errors: list[str] = []
        self._walk(instance, self.root, "$", errors)
        return sorted(errors)

    def _walk(self, inst: Any, schema: dict[str, Any], path: str,
              errors: list[str]) -> None:
        if "$ref" in schema:
            self._walk(inst, self._resolve(schema["$ref"]), path, errors)

        typ = schema.get("type")
        if typ is not None:
            names = [typ] if isinstance(typ, str) else [str(t) for t in typ]
            if not any(_is_type(inst, n) for n in names):
                errors.append(f"{path}: expected type {'|'.join(names)}, "
                              f"got {type(inst).__name__}")
                return  # further checks would be meaningless

        if "const" in schema and inst != schema["const"]:
            errors.append(f"{path}: expected const {schema['const']!r}, "
                          f"got {inst!r}")
        if "enum" in schema and inst not in schema["enum"]:
            errors.append(f"{path}: {inst!r} not in enum {schema['enum']!r}")

        if isinstance(inst, str):
            if "minLength" in schema and len(inst) < schema["minLength"]:
                errors.append(f"{path}: string shorter than minLength "
                              f"{schema['minLength']}")
            if "pattern" in schema and not re.search(schema["pattern"], inst):
                errors.append(f"{path}: {inst!r} does not match "
                              f"pattern {schema['pattern']!r}")
        if isinstance(inst, (int, float)) and not isinstance(inst, bool):
            if "minimum" in schema and inst < schema["minimum"]:
                errors.append(f"{path}: {inst} below minimum "
                              f"{schema['minimum']}")

        if isinstance(inst, dict):
            props = schema.get("properties", {})
            for key in schema.get("required", []):
                if key not in inst:
                    errors.append(f"{path}: missing required property {key!r}")
            for key, value in inst.items():
                if key in props:
                    self._walk(value, props[key], f"{path}.{key}", errors)
                    continue
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    errors.append(f"{path}: unexpected property {key!r}")
                elif isinstance(ap, dict):
                    self._walk(value, ap, f"{path}.{key}", errors)

        if isinstance(inst, list) and "items" in schema:
            for i, value in enumerate(inst):
                self._walk(value, schema["items"], f"{path}[{i}]", errors)


def validate(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Convenience wrapper around :class:`Validator`."""
    return Validator(schema).validate(instance)


def strict_validate(instance: Any, schema: dict[str, Any]) -> None:
    """Raise :class:`SchemaValidationError` if the instance is invalid."""
    errors = validate(instance, schema)
    if errors:
        raise SchemaValidationError(errors)


__all__ = [
    "SUPPORTED_KEYWORDS", "SchemaError", "SchemaValidationError",
    "Validator", "validate", "strict_validate",
]
