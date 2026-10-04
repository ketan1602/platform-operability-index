"""Zero-dependency token tracker: monkeypatches httpx (and httpx2) to capture LLM usage.

Call install() once at process startup (child_entry.py does this automatically).
Usage events are written to the POI_LEDGER file so the parent harness can sum them
across all trials. The patch is idempotent; installing twice has no effect.

Strategy
--------
1. Intercept the outgoing request and inject ``stream_options.include_usage=True`` for
   any streaming completion — AI Refinery only includes usage in SSE when asked.
2. For non-streaming responses (already buffered by httpx): read usage from _content.
3. For streaming responses: wrap response.stream so every chunk is captured; extract
   usage from the accumulated SSE after the stream exhausts.

Both ``httpx`` (used by openai <=2.x, LiteLLM, Strands) and ``httpx2`` (used by
openai >=3.x — LangGraph, AutoGen, OpenAI SDK) are patched when present.
"""
from __future__ import annotations

_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    try:
        import httpx
        _patch_module(httpx)
    except ImportError:
        pass
    try:
        import httpx2
        _patch_module(httpx2)
    except ImportError:
        pass


def _is_completion(url: str) -> bool:
    return "/chat/completions" in url


def _record(usage: dict) -> None:
    inp = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    out = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    if not (inp or out):
        return
    import os
    from harness.shared import ledger
    path_str = os.environ.get(ledger.LEDGER_ENV)
    if path_str:
        ledger.record("llm_usage", input_tokens=inp, output_tokens=out)


def _extract_usage(content: bytes) -> dict:
    """Parse usage from a plain JSON body or an SSE stream."""
    import json
    text = content.decode("utf-8", errors="ignore")
    try:
        return json.loads(text).get("usage", {}) or {}
    except Exception:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
            usage = obj.get("usage") or {}
            if usage:
                return usage
        except Exception:
            continue
    return {}


def _inject_usage_opt(request, httpx_mod):
    """Return request with stream_options.include_usage=True injected for SSE calls."""
    import json
    try:
        body = json.loads(request.content)
        if not body.get("stream") or (body.get("stream_options") or {}).get("include_usage"):
            return request
        body.setdefault("stream_options", {})["include_usage"] = True
        new_bytes = json.dumps(body).encode()
        hdr = {k: v for k, v in request.headers.items() if k.lower() != "content-length"}
        return httpx_mod.Request(request.method, request.url, headers=hdr, content=new_bytes)
    except Exception:
        return request


def _wrap_aiter_bytes(response) -> None:
    """Patch response.aiter_bytes to capture chunks and record usage when exhausted.

    This approach avoids touching response.stream directly, so httpx2's internal
    AsyncByteStream isinstance checks are never triggered.
    """
    if not hasattr(response, "aiter_bytes"):
        return
    _orig = response.aiter_bytes

    async def _capturing(*args, **kwargs):
        chunks: list[bytes] = []
        try:
            async for chunk in _orig(*args, **kwargs):
                chunks.append(chunk)
                yield chunk
        finally:
            usage = _extract_usage(b"".join(chunks))
            if usage:
                _record(usage)

    response.aiter_bytes = _capturing


def _patch_module(httpx_mod) -> None:
    """Patch both Client.send and AsyncClient.send on the given httpx-compatible module."""
    _patch_sync(httpx_mod)
    _patch_async(httpx_mod)


def _patch_sync(httpx_mod) -> None:
    _orig = httpx_mod.Client.send

    def _send(self, request, *args, **kwargs):
        if _is_completion(str(request.url)):
            request = _inject_usage_opt(request, httpx_mod)
        response = _orig(self, request, *args, **kwargs)
        if _is_completion(str(request.url)):
            try:
                if not hasattr(response, "_content"):
                    response.read()
                usage = _extract_usage(response.content)
                if usage:
                    _record(usage)
            except Exception:
                pass
        return response

    httpx_mod.Client.send = _send


def _patch_async(httpx_mod) -> None:
    _orig = httpx_mod.AsyncClient.send

    async def _send(self, request, *args, **kwargs):
        if _is_completion(str(request.url)):
            request = _inject_usage_opt(request, httpx_mod)
        response = await _orig(self, request, *args, **kwargs)
        if _is_completion(str(request.url)):
            try:
                if hasattr(response, "_content"):
                    # Non-streaming: already buffered by httpx before send() returned
                    usage = _extract_usage(response.content)
                    if usage:
                        _record(usage)
                else:
                    # Streaming SSE: wrap aiter_bytes to capture chunks transparently
                    _wrap_aiter_bytes(response)
            except Exception:
                pass
        return response

    httpx_mod.AsyncClient.send = _send
