from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from .exceptions import SchemaError, ValidationError

__all__ = [
    "Draft7Validator",
    "FormatChecker",
    "SchemaError",
    "ValidationError",
    "validate",
]


def _decode_json_pointer(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _resolve_ref(ref: str, root_schema: Any) -> Any:
    if not isinstance(ref, str) or not ref.startswith("#"):
        raise SchemaError(f"Only local JSON Pointer refs are supported: {ref!r}")
    if ref in ("#", "#/"):
        return root_schema

    target: Any = root_schema
    parts = [part for part in ref[2:].split("/") if part != ""]
    for part in parts:
        part = _decode_json_pointer(part)
        if isinstance(target, dict) and part in target:
            target = target[part]
            continue
        if isinstance(target, list):
            try:
                target = target[int(part)]
                continue
            except (ValueError, IndexError):
                raise SchemaError(f"Unresolvable JSON Pointer ref: {ref!r}") from None
        raise SchemaError(f"Unresolvable JSON Pointer ref: {ref!r}")
    return target


def _path_text(path: tuple[Any, ...]) -> str:
    if not path:
        return ""
    text = ""
    for part in path:
        if isinstance(part, int):
            text += f"[{part}]"
        elif text:
            text += f".{part}"
        else:
            text = str(part)
    return text


def _format_message(path: tuple[Any, ...], message: str) -> str:
    prefix = _path_text(path)
    return f"{prefix}: {message}" if prefix else message


def _is_type(instance: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(instance, dict)
    if schema_type == "array":
        return isinstance(instance, list)
    if schema_type == "string":
        return isinstance(instance, str)
    if schema_type == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if schema_type == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if schema_type == "boolean":
        return isinstance(instance, bool)
    if schema_type == "null":
        return instance is None
    return True


def _format_check(instance: Any, fmt: str) -> bool:
    if not isinstance(instance, str):
        return False
    if fmt == "date":
        try:
            date.fromisoformat(instance)
            return True
        except ValueError:
            return False
    if fmt == "date-time":
        try:
            datetime.fromisoformat(instance.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
    return True


class FormatChecker:
    """Minimal format checker for the formats used by this repository."""

    def __init__(self) -> None:
        self._checkers: dict[str, Any] = {}

    def checks(self, format_name: str):
        def decorator(func):
            self._checkers[format_name] = func
            return func

        return decorator

    def check(self, instance: Any, format_name: str) -> bool:
        checker = self._checkers.get(format_name)
        if checker is not None:
            return bool(checker(instance))
        return _format_check(instance, format_name)


class Draft7Validator:
    def __init__(self, schema: Any, *, format_checker: FormatChecker | None = None) -> None:
        self.schema = schema
        self.format_checker = format_checker
        self.check_schema(schema)

    @classmethod
    def check_schema(cls, schema: Any) -> None:
        if not isinstance(schema, (dict, bool)):
            raise SchemaError("Draft 7 schemas must be a mapping or boolean schema")

    def is_valid(self, instance: Any) -> bool:
        return not any(self.iter_errors(instance))

    def iter_errors(self, instance: Any):
        yield from self._iter_errors(instance, self.schema, (), self.schema)

    def _iter_errors(
        self,
        instance: Any,
        schema: Any,
        path: tuple[Any, ...],
        root_schema: Any,
    ):
        if schema is True:
            return
        if schema is False:
            yield ValidationError(_format_message(path, "False schema does not allow this value"), instance, schema, path)
            return
        if not isinstance(schema, dict):
            raise SchemaError("Schemas must be mappings, booleans, or local $ref targets")

        if "$ref" in schema:
            yield from self._iter_errors(instance, _resolve_ref(schema["$ref"], root_schema), path, root_schema)
            return

        if "allOf" in schema:
            for subschema in schema["allOf"]:
                yield from self._iter_errors(instance, subschema, path, root_schema)

        if "anyOf" in schema:
            if not any(self._is_valid(instance, subschema, root_schema) for subschema in schema["anyOf"]):
                yield ValidationError(_format_message(path, "is not valid under any of the given schemas"), instance, schema, path, "anyOf", schema["anyOf"])

        if "oneOf" in schema:
            valid_count = sum(1 for subschema in schema["oneOf"] if self._is_valid(instance, subschema, root_schema))
            if valid_count != 1:
                yield ValidationError(_format_message(path, f"is valid under {valid_count} schemas; expected exactly one"), instance, schema, path, "oneOf", schema["oneOf"])

        if "not" in schema and self._is_valid(instance, schema["not"], root_schema):
            yield ValidationError(_format_message(path, "should not be valid under the given schema"), instance, schema, path, "not", schema["not"])

        if "if" in schema:
            if self._is_valid(instance, schema["if"], root_schema):
                if "then" in schema:
                    yield from self._iter_errors(instance, schema["then"], path, root_schema)
            elif "else" in schema:
                yield from self._iter_errors(instance, schema["else"], path, root_schema)

        schema_type = schema.get("type")
        if schema_type is not None:
            if isinstance(schema_type, list):
                if not any(_is_type(instance, t) for t in schema_type):
                    yield ValidationError(_format_message(path, f"{instance!r} is not of any allowed type {schema_type!r}"), instance, schema, path, "type", schema_type)
                    return
            elif not _is_type(instance, schema_type):
                yield ValidationError(_format_message(path, f"{instance!r} is not of type {schema_type!r}"), instance, schema, path, "type", schema_type)
                return

        if "enum" in schema and instance not in schema["enum"]:
            yield ValidationError(_format_message(path, f"{instance!r} is not one of {schema['enum']!r}"), instance, schema, path, "enum", schema["enum"])

        if "const" in schema and instance != schema["const"]:
            yield ValidationError(_format_message(path, f"{instance!r} does not equal the expected constant"), instance, schema, path, "const", schema["const"])

        if isinstance(instance, str):
            if "minLength" in schema and len(instance) < schema["minLength"]:
                yield ValidationError(_format_message(path, f"String is shorter than the minimum length of {schema['minLength']}"), instance, schema, path, "minLength", schema["minLength"])
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                yield ValidationError(_format_message(path, f"String is longer than the maximum length of {schema['maxLength']}"), instance, schema, path, "maxLength", schema["maxLength"])
            if "pattern" in schema and re.search(schema["pattern"], instance) is None:
                yield ValidationError(_format_message(path, f"{instance!r} does not match pattern {schema['pattern']!r}"), instance, schema, path, "pattern", schema["pattern"])
            if "format" in schema and self.format_checker is not None and not self.format_checker.check(instance, schema["format"]):
                yield ValidationError(_format_message(path, f"{instance!r} is not a valid {schema['format']}"), instance, schema, path, "format", schema["format"])

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                yield ValidationError(_format_message(path, f"{instance!r} is less than the minimum of {schema['minimum']}"), instance, schema, path, "minimum", schema["minimum"])
            if "maximum" in schema and instance > schema["maximum"]:
                yield ValidationError(_format_message(path, f"{instance!r} is greater than the maximum of {schema['maximum']}"), instance, schema, path, "maximum", schema["maximum"])

        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < schema["minItems"]:
                yield ValidationError(_format_message(path, f"Array has fewer than the minimum of {schema['minItems']} items"), instance, schema, path, "minItems", schema["minItems"])
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                yield ValidationError(_format_message(path, f"Array has more than the maximum of {schema['maxItems']} items"), instance, schema, path, "maxItems", schema["maxItems"])

            items = schema.get("items")
            if isinstance(items, list):
                for index, item_schema in enumerate(items):
                    if index < len(instance):
                        yield from self._iter_errors(instance[index], item_schema, path + (index,), root_schema)
            elif items is not None:
                for index, item in enumerate(instance):
                    yield from self._iter_errors(item, items, path + (index,), root_schema)

        if isinstance(instance, dict):
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    yield ValidationError(_format_message(path + (key,), "is a required property"), instance, schema, path + (key,), "required", required)

            for key, value in instance.items():
                if key in properties:
                    yield from self._iter_errors(value, properties[key], path + (key,), root_schema)

            additional = schema.get("additionalProperties", True)
            if additional is False:
                for key in instance:
                    if key not in properties:
                        yield ValidationError(_format_message(path + (key,), "Additional properties are not allowed"), instance, schema, path + (key,), "additionalProperties", False)
            elif isinstance(additional, dict):
                for key in instance:
                    if key not in properties:
                        yield from self._iter_errors(instance[key], additional, path + (key,), root_schema)

    def _is_valid(self, instance: Any, schema: Any, root_schema: Any) -> bool:
        return not any(self._iter_errors(instance, schema, (), root_schema))


def validate(instance: Any, schema: Any, *, format_checker: FormatChecker | None = None) -> None:
    validator = Draft7Validator(schema, format_checker=format_checker)
    errors = list(validator.iter_errors(instance))
    if errors:
        raise errors[0]
