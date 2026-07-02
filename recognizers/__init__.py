"""Construction de l'AnalyzerEngine Presidio pour le Tier 1.

Le registry n'embarque QUE les recognizers pattern du Tier 1. Le NLP engine
est un pipeline spaCy `fr` vide (les patterns n'en ont pas besoin) : pour le
Tier 2, il suffira de remplacer `spacy.blank("fr")` par un modèle
`fr_core_news_*` et d'ajouter les recognizers NER au registry — sans refactor.
"""

import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import SpacyNlpEngine

from config import Settings

from .email import EmailRecognizer
from .iban import IbanFrRecognizer
from .nir import NirRecognizer
from .phone import PhoneFrRecognizer
from .pro_ids import (
    AdeliRecognizer,
    RppsRecognizer,
    SirenRecognizer,
    SiretRecognizer,
)

# Seuil : les résultats invalidés par checksum ont un score 0 et doivent être
# écartés ; les patterns valides scorent >= 0.45.
SCORE_THRESHOLD = 0.35


class _BlankFrNlpEngine(SpacyNlpEngine):
    """Pipeline spaCy fr vide — Tier 1 = patterns uniquement, pas de NER."""

    def __init__(self):
        try:
            super().__init__(models=[{"lang_code": "fr", "model_name": "blank-fr"}])
        except Exception:
            # Selon la version de presidio, __init__ peut tenter de charger le
            # modèle : on installe le pipeline vide dans tous les cas.
            pass
        self.nlp = {"fr": spacy.blank("fr")}

    def load(self) -> None:
        self.nlp = {"fr": spacy.blank("fr")}


def build_analyzer(settings: Settings) -> AnalyzerEngine:
    registry = RecognizerRegistry(supported_languages=["fr"])
    recognizers = [
        EmailRecognizer(),
        PhoneFrRecognizer(),
        NirRecognizer(),
        IbanFrRecognizer(),
    ]
    if settings.enable_rpps:
        recognizers.append(RppsRecognizer())
    if settings.enable_adeli:
        recognizers.append(AdeliRecognizer())
    if settings.enable_siren_siret:
        recognizers.append(SirenRecognizer())
        recognizers.append(SiretRecognizer())
    for recognizer in recognizers:
        registry.add_recognizer(recognizer)

    return AnalyzerEngine(
        registry=registry,
        nlp_engine=_BlankFrNlpEngine(),
        supported_languages=["fr"],
        default_score_threshold=SCORE_THRESHOLD,
    )
