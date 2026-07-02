"""Tier 2 — NER spaCy fr : PERSON (PER) et LOCATION (LOC).

⚠️ Le NER est PROBABILISTE : aucune garantie de capture à 100 %.
spaCy ne fournit pas de confiance par entité — Presidio assigne un score
fixe (NER_DEFAULT_SCORE) ; NER_SCORE_THRESHOLD filtre en aval (surfaces.py),
prêt pour un futur modèle exposant de vrais scores.
"""

from presidio_analyzer.nlp_engine import NerModelConfiguration, SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

NER_MODEL_NAME = "fr_core_news_lg"
NER_DEFAULT_SCORE = 0.85

# Entités issues du NER (soumises au seuil NER_SCORE_THRESHOLD),
# par opposition aux entités pattern du Tier 1 et à ADDRESS.
NER_ENTITIES = frozenset({"PERSON", "LOCATION"})


def _ner_configuration() -> NerModelConfiguration:
    return NerModelConfiguration(
        model_to_presidio_entity_mapping={
            "PER": "PERSON",
            "PERSON": "PERSON",
            "LOC": "LOCATION",
            "GPE": "LOCATION",
        },
        labels_to_ignore=["ORG", "MISC"],  # hors scope Tier 2
        default_score=NER_DEFAULT_SCORE,
    )


class FrNerNlpEngine(SpacyNlpEngine):
    """SpacyNlpEngine sur fr_core_news_lg avec mapping PER/LOC → PERSON/LOCATION."""

    def __init__(self):
        super().__init__(
            models=[{"lang_code": "fr", "model_name": NER_MODEL_NAME}],
            ner_model_configuration=_ner_configuration(),
        )


def build_ner_recognizer(enable_location: bool) -> SpacyRecognizer:
    entities = ["PERSON"] + (["LOCATION"] if enable_location else [])
    return SpacyRecognizer(
        supported_language="fr",
        supported_entities=entities,
    )
