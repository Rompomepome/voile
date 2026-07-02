"""Intégration bout en bout, upstream mocké — critère d'acceptation du brief :

(a) l'upstream ne reçoit QUE des jetons (y compris system et content blocks) ;
(b) l'appelant récupère les valeurs réelles ;
(c) le log d'audit ne contient aucune valeur ;
(d) stream: true → 400 propre ;
(e) anti-collision des jetons.

Données synthétiques uniquement.
"""

import json
import re

import httpx

EMAIL = "jean.dupont@example.org"
PHONE = "06 12 34 56 78"
NIR_2A = "185052A00404240"  # NIR corse, clé valide
IBAN_GROUPE = "FR76 3000 6000 0112 3456 7890 189"
SIRET = "73282932000033"
LITERAL_TOKEN = "<<PII:EMAIL:7>>"  # motif déjà présent dans le texte source

RAW_VALUES = [EMAIL, PHONE, NIR_2A, IBAN_GROUPE, SIRET]

IMAGE_BLOCK = {
    "type": "image",
    "source": {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="},
}


def full_request_body() -> dict:
    """PII dans le system (string) ET dans les messages (string + blocs)."""
    return {
        "model": "claude-sonnet-4-6",
        "max_tokens": 256,
        "temperature": 0.2,
        "system": f"Dossier patient. Contact {EMAIL}, NIR {NIR_2A}.",
        "messages": [
            {
                "role": "user",
                "content": f"Rappeler le {PHONE}, virement sur {IBAN_GROUPE}, "
                f"copie à {EMAIL}.",
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": f"SIRET {SIRET} bien noté."}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Le motif {LITERAL_TOKEN} doit rester intact.",
                    },
                    IMAGE_BLOCK,
                ],
            },
        ],
    }


class TestBoucleComplete:
    def test_upstream_ne_recoit_que_des_jetons(self, gateway, upstream):
        response = gateway.post(
            "/v1/messages",
            json=full_request_body(),
            headers={"x-api-key": "sk-client", "anthropic-version": "2023-06-01"},
        )
        assert response.status_code == 200

        sent = upstream.sent_body()
        sent_str = json.dumps(sent, ensure_ascii=False)

        # (a) aucune valeur réelle côté upstream, nulle part
        for raw in RAW_VALUES:
            assert raw not in sent_str, raw
        assert IBAN_GROUPE.replace(" ", "") not in sent_str

        # jetons présents dans le system ET les blocs
        assert "<<PII:EMAIL:" in sent["system"]
        assert "<<PII:NIR:" in sent["system"]
        assert "<<PII:PHONE_FR:" in sent["messages"][0]["content"]
        assert "<<PII:IBAN_FR:" in sent["messages"][0]["content"]
        assert "<<PII:SIRET:" in sent["messages"][1]["content"][0]["text"]

        # cohérence intra-requête : même email (system + message 0) → même jeton
        email_tokens = set(re.findall(r"<<PII:EMAIL:\d+>>", sent_str))
        assert len(email_tokens) == 1

        # (e) anti-collision : le littéral est échappé, jamais confondu
        assert LITERAL_TOKEN not in sent_str
        assert "<<PII-RAW:EMAIL:7>>" in sent["messages"][2]["content"][0]["text"]

        # les blocs non-text et les autres champs passent tels quels
        assert sent["messages"][2]["content"][1] == IMAGE_BLOCK
        assert sent["model"] == "claude-sonnet-4-6"
        assert sent["max_tokens"] == 256
        assert sent["temperature"] == 0.2

    def test_appelant_recupere_les_valeurs_reelles(self, gateway):
        response = gateway.post(
            "/v1/messages", json=full_request_body(), headers={"x-api-key": "sk-c"}
        )
        assert response.status_code == 200
        text = response.json()["content"][0]["text"]

        # (b) l'écho upstream ne contenait que des jetons ; l'appelant
        # récupère les valeurs réelles après ré-identification
        for raw in RAW_VALUES:
            assert raw in text, raw
        # (e) le motif littéral est restauré à l'identique
        assert LITERAL_TOKEN in text
        assert "<<PII-RAW:" not in text
        # plus aucun jeton résiduel connu
        assert not re.findall(r"<<PII:(?:EMAIL|NIR|PHONE_FR|IBAN_FR|SIRET):[1-5]>>", text)

    def test_audit_sans_aucune_valeur(self, gateway):
        gateway.post("/v1/messages", json=full_request_body(), headers={"x-api-key": "k"})

        content = gateway.audit_file.read_text()
        # (c) aucune valeur, ni fragment de prompt/réponse
        for raw in RAW_VALUES:
            assert raw not in content
        assert "Dossier patient" not in content
        assert "bien noté" not in content

        entry = json.loads(content.strip().splitlines()[-1])
        assert entry["status"] == 200
        assert entry["latency_ms"] >= 0
        assert entry["pii_counts"]["EMAIL"] == 2  # system + message 0
        assert entry["pii_counts"]["NIR"] == 1
        assert entry["pii_counts"]["PHONE_FR"] == 1
        assert entry["pii_counts"]["IBAN_FR"] == 1
        assert entry["pii_counts"]["SIRET"] == 1
        assert sorted(entry["pii_types"]) == entry["pii_types"]

    def test_system_en_blocs(self, gateway, upstream):
        body = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "system": [
                {"type": "text", "text": f"Contact : {EMAIL}"},
                {"type": "text", "text": f"NIR : {NIR_2A}"},
            ],
            "messages": [{"role": "user", "content": "Bonjour"}],
        }
        response = gateway.post("/v1/messages", json=body, headers={"x-api-key": "k"})
        assert response.status_code == 200

        sent = upstream.sent_body()
        assert EMAIL not in json.dumps(sent)
        assert NIR_2A not in json.dumps(sent)
        assert "<<PII:EMAIL:1>>" in sent["system"][0]["text"]
        assert "<<PII:NIR:1>>" in sent["system"][1]["text"]


class TestTier2Ner:
    PERSON = "Camille Moreau"
    ADDRESS_VOIE = "12 rue de la Paix"
    ADDRESS_CP = "75002 Paris"
    VILLE = "Lyon"

    def body(self) -> dict:
        return {
            "model": "claude-sonnet-4-6",
            "max_tokens": 128,
            "system": "Tu rédiges des courriers administratifs.",
            "messages": [
                {
                    "role": "user",
                    "content": f"Courrier pour {self.PERSON}, domiciliée "
                    f"{self.ADDRESS_VOIE}, {self.ADDRESS_CP}. "
                    f"Elle part à {self.VILLE} lundi.",
                },
            ],
        }

    def test_person_location_address_bout_en_bout(self, gateway, upstream):
        response = gateway.post(
            "/v1/messages", json=self.body(), headers={"x-api-key": "k"}
        )
        assert response.status_code == 200

        sent_str = json.dumps(upstream.sent_body(), ensure_ascii=False)
        for raw in [self.PERSON, self.ADDRESS_VOIE, self.ADDRESS_CP, self.VILLE]:
            assert raw not in sent_str, raw
        assert "<<PII:PERSON:1>>" in sent_str
        assert "<<PII:ADDRESS:1>>" in sent_str
        assert "<<PII:ADDRESS:2>>" in sent_str
        assert "<<PII:LOCATION:1>>" in sent_str

        # l'appelant récupère les valeurs réelles
        text = response.json()["content"][0]["text"]
        for raw in [self.PERSON, self.ADDRESS_VOIE, self.ADDRESS_CP, self.VILLE]:
            assert raw in text, raw

    def test_audit_tier2_sans_valeur(self, gateway):
        gateway.post("/v1/messages", json=self.body(), headers={"x-api-key": "k"})

        content = gateway.audit_file.read_text()
        for raw in [self.PERSON, self.ADDRESS_VOIE, self.ADDRESS_CP, self.VILLE]:
            assert raw not in content

        entry = json.loads(content.strip().splitlines()[-1])
        assert entry["pii_counts"]["PERSON"] == 1
        assert entry["pii_counts"]["ADDRESS"] == 2
        assert entry["pii_counts"]["LOCATION"] == 1


class TestStream:
    def test_stream_true_400_propre(self, gateway, upstream):
        body = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": f"Contact {EMAIL}"}],
        }
        response = gateway.post("/v1/messages", json=body, headers={"x-api-key": "k"})

        # (d) 400 explicite, pas de crash, upstream jamais appelé
        assert response.status_code == 400
        error = response.json()
        assert error["type"] == "error"
        assert error["error"]["type"] == "invalid_request_error"
        assert "streaming" in error["error"]["message"].lower()
        assert upstream.requests == []


class TestCleApi:
    def test_cle_client_forwardee(self, gateway, upstream):
        gateway.post(
            "/v1/messages",
            json=full_request_body(),
            headers={"x-api-key": "sk-client-123"},
        )
        assert upstream.requests[0].headers["x-api-key"] == "sk-client-123"

    def test_fallback_cle_env(self, gateway, upstream):
        gateway.post("/v1/messages", json=full_request_body())
        assert upstream.requests[0].headers["x-api-key"] == "sk-env-fallback"

    def test_headers_anthropic_forwardes(self, gateway, upstream):
        gateway.post(
            "/v1/messages",
            json=full_request_body(),
            headers={
                "x-api-key": "k",
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "beta-feature-1",
            },
        )
        headers = upstream.requests[0].headers
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["anthropic-beta"] == "beta-feature-1"


class TestErreursUpstream:
    def test_erreur_4xx_transmise_telle_quelle(self, gateway, upstream):
        error_body = {
            "type": "error",
            "error": {"type": "rate_limit_error", "message": "Ralentissez."},
        }
        upstream.responder = lambda request: httpx.Response(429, json=error_body)

        response = gateway.post(
            "/v1/messages", json=full_request_body(), headers={"x-api-key": "k"}
        )
        assert response.status_code == 429
        assert response.json() == error_body

    def test_erreur_5xx_transmise_telle_quelle(self, gateway, upstream):
        upstream.responder = lambda request: httpx.Response(
            529, json={"type": "error", "error": {"type": "overloaded_error", "message": "x"}}
        )
        response = gateway.post(
            "/v1/messages", json=full_request_body(), headers={"x-api-key": "k"}
        )
        assert response.status_code == 529

    def test_upstream_injoignable_502(self, gateway, upstream):
        def boom(request):
            raise httpx.ConnectError("connexion refusée", request=request)

        upstream.responder = boom
        response = gateway.post(
            "/v1/messages", json=full_request_body(), headers={"x-api-key": "k"}
        )
        assert response.status_code == 502
        assert response.json()["error"]["type"] == "upstream_error"

    def test_json_invalide_400(self, gateway):
        response = gateway.post(
            "/v1/messages",
            content=b"pas du json",
            headers={"x-api-key": "k", "content-type": "application/json"},
        )
        assert response.status_code == 400
