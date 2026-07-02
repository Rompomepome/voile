"""Gateway PII « Voile » — slice vertical Tier 1.

Proxy local compatible avec POST /v1/messages de l'API Anthropic :
pseudonymise (réversible) les identifiants Tier 1 avant l'envoi upstream,
ré-identifie la réponse au retour. Streaming non supporté en v0 (→ 400).
"""

import time
from collections import Counter
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from presidio_anonymizer import AnonymizerEngine

import audit
from config import load_settings
from recognizers import build_analyzer
from surfaces import make_pseudonymizer, pseudonymize_request, reidentify_response
from tokenizer import TokenMapper

DEFAULT_ANTHROPIC_VERSION = "2023-06-01"

# Headers client transmis tels quels à l'upstream (x-api-key traité à part).
_FORWARDED_HEADERS = ("anthropic-version", "anthropic-beta")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    audit.configure(settings.audit_log_file)
    app.state.settings = settings
    app.state.analyzer = build_analyzer(settings)
    app.state.anonymizer = AnonymizerEngine()
    app.state.client = httpx.AsyncClient(
        base_url=settings.upstream_base_url,
        timeout=settings.upstream_timeout_s,
    )
    yield
    await app.state.client.aclose()


app = FastAPI(title="voile", lifespan=lifespan)


def _error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": error_type, "message": message}},
    )


def _forward_headers(request: Request, settings) -> dict[str, str]:
    headers = {"content-type": "application/json"}
    for name in _FORWARDED_HEADERS:
        value = request.headers.get(name)
        if value is not None:
            headers[name] = value
    headers.setdefault("anthropic-version", DEFAULT_ANTHROPIC_VERSION)
    # Clé API : celle du client si présente, sinon fallback env.
    api_key = request.headers.get("x-api-key") or settings.anthropic_api_key
    if api_key:
        headers["x-api-key"] = api_key
    return headers


@app.post("/v1/messages")
async def messages(request: Request) -> Response:
    started = time.perf_counter()
    settings = request.app.state.settings

    try:
        body = await request.json()
    except Exception:
        return _error_response(400, "invalid_request_error", "Corps JSON invalide.")
    if not isinstance(body, dict):
        return _error_response(400, "invalid_request_error", "Corps JSON invalide.")

    if body.get("stream"):
        return _error_response(
            400,
            "invalid_request_error",
            "Streaming non supporté en v0 par la gateway voile. "
            "Réessayez avec stream=false.",
        )

    # Mapping jeton⇄valeur : en mémoire, scope de CETTE requête uniquement.
    mapper = TokenMapper()
    stats: Counter = Counter()
    pseudonymize = make_pseudonymizer(
        request.app.state.analyzer, request.app.state.anonymizer, mapper, stats
    )
    safe_body = pseudonymize_request(body, pseudonymize)

    try:
        upstream = await request.app.state.client.post(
            "/v1/messages",
            json=safe_body,
            headers=_forward_headers(request, settings),
        )
    except httpx.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        audit.log_request(dict(stats), latency_ms, 502)
        return _error_response(
            502, "upstream_error", f"Upstream injoignable : {type(exc).__name__}."
        )

    latency_ms = (time.perf_counter() - started) * 1000

    if upstream.status_code >= 400:
        # Erreurs upstream transmises telles quelles à l'appelant.
        audit.log_request(dict(stats), latency_ms, upstream.status_code)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    data = upstream.json()
    reidentify_response(data, mapper)
    audit.log_request(dict(stats), latency_ms, upstream.status_code)
    return JSONResponse(status_code=upstream.status_code, content=data)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=load_settings().port)
