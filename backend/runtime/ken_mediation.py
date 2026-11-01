"""A complete bounded Ken catalog, mediated by the host before native admission."""

import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from backend.runtime.business_mediation import McpTools, _failure

KEN_NAMES = frozenset(
    {"ken_find", "ken_read", "ken_recall", "ken_related", "ken_remember"}
)


class KenNotReady(ValueError):
    """No native thread/turn may rely on this incomplete or invalid catalog."""


def _validator(schema):
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise KenNotReady("Ken tool arguments require an object schema")
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(
        "", Resource.from_contents(schema, default_specification=DRAFT202012)
    )
    resolver = registry.resolver()
    pending = [schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            for keyword in ("$ref", "$dynamicRef"):
                if keyword in node:
                    reference = node[keyword]
                    if not reference.startswith("#"):
                        raise KenNotReady("Ken schemas must resolve locally")
                    resolver.lookup(reference)
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return Draft202012Validator(schema, registry=registry)


class KenTools(McpTools):
    @classmethod
    async def connect(cls, peer, *, active=lambda: True):
        catalog, seen, cursors = {}, set(), set()
        cursor = None
        for _ in range(8):
            if not active():
                raise KenNotReady("Ken admission authority ended")
            result = (
                await peer.list_tools(cursor=cursor)
                if cursor is not None
                else await peer.list_tools()
            )
            if not active():
                raise KenNotReady("Ken admission authority ended")
            for tool in result.tools:
                if (
                    not isinstance(tool.name, str)
                    or tool.name in seen
                    or len(seen) >= 128
                ):
                    raise KenNotReady("Ambiguous or oversized Ken catalog")
                seen.add(tool.name)
                if tool.name in KEN_NAMES:
                    row = {
                        "type": "function",
                        "name": tool.name,
                        "description": tool.description or tool.name,
                        "inputSchema": tool.inputSchema,
                    }
                    # Retain an independent snapshot of the advertised schema.
                    try:
                        encoded = json.dumps(row, allow_nan=False)
                        if len(encoded.encode()) > 200000:
                            raise KenNotReady("Ken tool schema exceeds catalog budget")
                        catalog[tool.name] = json.loads(encoded)
                    except (ValueError, TypeError, RecursionError):
                        raise KenNotReady("Invalid Ken catalog encoding") from None
            cursor = getattr(result, "nextCursor", None)
            if cursor is None:
                break
            if (
                not isinstance(cursor, str)
                or not 0 < len(cursor) <= 1024
                or cursor in cursors
            ):
                raise KenNotReady("Invalid Ken catalog pagination")
            cursors.add(cursor)
        else:
            raise KenNotReady("Ken catalog pagination exceeded admission budget")
        if set(catalog) != KEN_NAMES:
            raise KenNotReady("All five required Ken tools must be available")
        try:
            validators = {
                name: _validator(row["inputSchema"]) for name, row in catalog.items()
            }
        except (SchemaError, Unresolvable, ValueError, RecursionError):
            raise KenNotReady("Invalid or unresolvable Ken argument schema") from None
        tools = cls(peer, [catalog[name] for name in sorted(catalog)], active)
        tools._validators = validators
        return tools

    async def call(self, params):
        if (
            not isinstance(params, dict)
            or not isinstance(params.get("tool"), str)
            or params["tool"] not in self._validators
        ):
            return _failure("Unknown Ken tool or invalid argument envelope")
        try:
            if (
                len(json.dumps(params.get("arguments"), allow_nan=False).encode())
                > 200000
            ):
                return _failure("Ken arguments exceed the admitted wire budget")
            self._validators[params["tool"]].validate(params.get("arguments"))
        except (ValidationError, Unresolvable, RecursionError, ValueError, TypeError):
            return _failure("Ken arguments do not match the admitted schema")
        return await super().call(params)
