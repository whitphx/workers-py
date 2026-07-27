from http import HTTPMethod
from typing import Any, Unpack

import js
from js import Object
from pyodide.ffi import JsException, to_js

from .request import Request
from .response import Response
from .types import FetchKwargs


async def _raw_fetch(request: "str | js.Request", **kwargs: Any) -> "js.Response":
    # Call the fetcher (or js.fetch) directly instead of pyodide.http.pyfetch:
    # pyfetch unconditionally creates an AbortController and attaches its
    # signal to the request, and the only reference to that controller is the
    # Python FetchResponse wrapper — which fetch() below discards immediately,
    # and handlers drop when they return. After that, nothing keeps the
    # controller alive, and on deployed Workers the still-open subrequest is
    # canceled ("Canceled" in wrangler tail): a WebSocket upgrade proxied to a
    # Durable Object stub or a streaming/SSE body dies right after the handler
    # returns. Local dev does not reproduce this (GC/context timing differs),
    # so the failure is edge-only. Callers that want cancellation can pass
    # their own signal in kwargs; it flows through unchanged.
    custom_fetch = kwargs.pop("fetcher", None) or js.fetch
    try:
        return await custom_fetch(
            request, to_js(kwargs, dict_converter=Object.fromEntries)
        )
    except JsException as e:
        raise OSError(e.message) from None


async def fetch(
    resource: "str | Request | js.Request",
    **other_options: Unpack[FetchKwargs],
) -> Response:
    if isinstance(resource, Request):
        resource = resource.js_object
    if "method" in other_options and isinstance(other_options["method"], HTTPMethod):
        other_options["method"] = other_options["method"].value

    js_resp = await _raw_fetch(resource, **other_options)
    return Response(js_resp)
