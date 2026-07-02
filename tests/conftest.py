"""Fixtures partagées. Toutes les données de test sont SYNTHÉTIQUES
(clés NIR/IBAN/SIREN/SIRET calculées, jamais de vraies données)."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from config import Settings
from recognizers import build_analyzer


def make_settings(**overrides) -> Settings:
    """Défauts TEST : Tier 2 (NER/ADDRESS) désactivé, contrairement à la prod —
    les tests Tier 1 restent purs ; les tests Tier 2 activent explicitement."""
    defaults = dict(
        anthropic_api_key=None,
        upstream_base_url="https://upstream.test",
        enable_rpps=True,
        enable_adeli=True,
        enable_siren_siret=True,
        enable_ner=False,
        enable_location=False,
        enable_address=False,
        ner_score_threshold=0.4,
        upstream_timeout_s=5.0,
        port=8080,
        audit_log_file=None,
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(scope="session")
def analyzer():
    """Analyzer avec tous les recognizers Tier 1 activés (NER off)."""
    return build_analyzer(make_settings())


@pytest.fixture(scope="session")
def analyzer_ner():
    """Analyzer complet Tier 1 + Tier 2 (NER, LOCATION, ADDRESS)."""
    return build_analyzer(
        make_settings(enable_ner=True, enable_location=True, enable_address=True)
    )


def _collect_texts(body: dict) -> list[str]:
    """Toutes les surfaces texte d'une requête (system + messages)."""
    texts = []
    system = body.get("system")
    if isinstance(system, str):
        texts.append(system)
    elif isinstance(system, list):
        texts += [
            b["text"] for b in system if isinstance(b, dict) and b.get("type") == "text"
        ]
    for message in body.get("messages", []):
        content = message.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            texts += [
                b["text"]
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
    return texts


def echo_responder(request: httpx.Request) -> httpx.Response:
    """Upstream mocké : renvoie en écho toutes les surfaces texte reçues
    (donc les jetons), comme le ferait un modèle qui recopie les identifiants."""
    body = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "id": "msg_test_01",
            "type": "message",
            "role": "assistant",
            "model": body.get("model", "claude-sonnet-4-6"),
            "content": [{"type": "text", "text": "\n".join(_collect_texts(body))}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )


class MockUpstream:
    """Capture les requêtes envoyées à l'upstream et pilote la réponse."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.responder = echo_responder

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responder(request)

    def sent_body(self, index: int = 0) -> dict:
        return json.loads(self.requests[index].content)


@pytest.fixture()
def upstream():
    return MockUpstream()


@pytest.fixture()
def gateway(monkeypatch, tmp_path, upstream):
    """Gateway complète avec upstream mocké et audit log dans un fichier temp."""
    audit_file = tmp_path / "audit.log"
    monkeypatch.setenv("UPSTREAM_BASE_URL", "https://upstream.test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-fallback")
    monkeypatch.setenv("AUDIT_LOG_FILE", str(audit_file))

    import main

    with TestClient(main.app) as client:
        # Redirige le client httpx du lifespan vers l'upstream mocké.
        main.app.state.client._transport = httpx.MockTransport(upstream.handler)
        client.audit_file = audit_file
        yield client
