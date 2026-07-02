"""Tokenisation réversible : cohérence intra-requête et anti-collision."""

import re
from collections import Counter

from presidio_anonymizer import AnonymizerEngine

from surfaces import make_pseudonymizer
from tokenizer import (
    TOKEN_RE,
    TokenMapper,
    escape_preexisting_tokens,
    unescape_tokens,
)

EMAIL = "jean.dupont@example.org"
EMAIL_2 = "marie.martin@example.org"


class TestTokenMapper:
    def test_meme_valeur_meme_jeton(self):
        mapper = TokenMapper()
        assert mapper.token_for("EMAIL", EMAIL) == mapper.token_for("EMAIL", EMAIL)

    def test_valeurs_differentes_jetons_differents(self):
        mapper = TokenMapper()
        t1 = mapper.token_for("EMAIL", EMAIL)
        t2 = mapper.token_for("EMAIL", EMAIL_2)
        assert t1 == "<<PII:EMAIL:1>>"
        assert t2 == "<<PII:EMAIL:2>>"

    def test_compteurs_par_type(self):
        mapper = TokenMapper()
        assert mapper.token_for("EMAIL", EMAIL) == "<<PII:EMAIL:1>>"
        assert mapper.token_for("NIR", "185057800608491") == "<<PII:NIR:1>>"

    def test_detokenize_round_trip(self):
        mapper = TokenMapper()
        token = mapper.token_for("EMAIL", EMAIL)
        assert mapper.detokenize(f"Écrire à {token} demain") == f"Écrire à {EMAIL} demain"

    def test_jeton_inconnu_laisse_tel_quel(self):
        mapper = TokenMapper()
        assert mapper.detokenize("Voici <<PII:EMAIL:42>>") == "Voici <<PII:EMAIL:42>>"

    def test_repr_sans_valeur(self):
        mapper = TokenMapper()
        mapper.token_for("EMAIL", EMAIL)
        assert EMAIL not in repr(mapper)


class TestAntiCollision:
    def test_escape_unescape(self):
        source = "littéral <<PII:EMAIL:9>> dans le texte"
        escaped = escape_preexisting_tokens(source)
        assert "<<PII:EMAIL:9>>" not in escaped
        assert "<<PII-RAW:EMAIL:9>>" in escaped
        assert unescape_tokens(escaped) == source

    def test_token_re_ignore_les_echappes(self):
        assert TOKEN_RE.findall("<<PII-RAW:EMAIL:9>>") == []

    def test_collision_complete(self, analyzer):
        """Le texte source contient déjà <<PII:EMAIL:1>> — exactement le jeton
        que le mapper va générer. Sans échappement, la ré-identification
        confondrait le littéral et le jeton."""
        mapper = TokenMapper()
        stats = Counter()
        pseudo = make_pseudonymizer(analyzer, AnonymizerEngine(), mapper, stats)

        source = f"Motif <<PII:EMAIL:1>> à conserver, contacter {EMAIL}."
        tokenized = pseudo(source)

        # côté upstream : le littéral est échappé, l'email remplacé par un jeton
        assert EMAIL not in tokenized
        assert "<<PII-RAW:EMAIL:1>>" in tokenized
        assert TOKEN_RE.findall(tokenized) == ["<<PII:EMAIL:1>>"]

        # côté retour : détokenisation puis restauration du littéral
        restored = unescape_tokens(mapper.detokenize(tokenized))
        assert restored == source


class TestCoherenceIntraRequete:
    def test_meme_valeur_deux_surfaces(self, analyzer):
        """Même email dans deux surfaces (system + message) → même jeton."""
        mapper = TokenMapper()
        pseudo = make_pseudonymizer(analyzer, AnonymizerEngine(), mapper, Counter())

        out1 = pseudo(f"System : contact {EMAIL}")
        out2 = pseudo(f"Message : merci d'écrire à {EMAIL} vite")

        tokens1 = re.findall(r"<<PII:EMAIL:\d+>>", out1)
        tokens2 = re.findall(r"<<PII:EMAIL:\d+>>", out2)
        assert tokens1 == tokens2 == ["<<PII:EMAIL:1>>"]

    def test_stats_comptees(self, analyzer):
        mapper = TokenMapper()
        stats = Counter()
        pseudo = make_pseudonymizer(analyzer, AnonymizerEngine(), mapper, stats)
        pseudo(f"Écrire à {EMAIL} et à {EMAIL_2}")
        assert stats["EMAIL"] == 2
