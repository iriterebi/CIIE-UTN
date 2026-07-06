"""Definiciones de tipos compartidas entre módulos."""

from typing import Any, NotRequired, TypedDict


# --- Status ---

type StatusData = dict[str, Any]

class CoreStatusData(TypedDict):
    core: str
    local: StatusData
    remote: StatusData


# --- JSON-RPC 2.0 ---

class JsonRpcRequest[T](TypedDict):
    jsonrpc: str
    method: str
    params: NotRequired[T]
    id: Any

class JsonRpcResponse[T](TypedDict):
    jsonrpc: str
    result: T
    error: NotRequired[dict[str, Any]]
    id: Any
