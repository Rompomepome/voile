"""Construction de l'AnalyzerEngine Presidio.

Tier 1 : recognizers pattern (email, tél, NIR, IBAN, RPPS/ADELI/SIREN/SIRET)
+ ADDRESS (pattern, indépendant du NER).
Tier 2 : ENABLE_NER=true → NLP engine fr_core_news_lg + recognizer NER
(PERSON, LOCATION). ENABLE_NER=false → pipeline spaCy vide, patterns seuls.
"""

from functools import lru_cache

import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import SpacyNlpEngine

from config import Settings

from .address import AddressRecognizer
from .email import EmailRecognizer
from .iban import IbanFrRecognizer
from .ner import FrNerNlpEngine, build_ner_recognizer
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


@lru_cache(maxsize=8)
def build_analyzer(settings: Settings) -> AnalyzerEngine:
    """Settings est un dataclass frozen (hashable) : mêmes réglages → même
    engine réutilisé. Évite de recharger fr_core_news_lg (~545 MB) à chaque
    construction ; l'engine est sans état côté analyse."""
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
    if settings.enable_address:
        recognizers.append(AddressRecognizer())
    if settings.enable_ner:
        recognizers.append(build_ner_recognizer(settings.enable_location))
        nlp_engine = FrNerNlpEngine()
    else:
        nlp_engine = _BlankFrNlpEngine()
    for recognizer in recognizers:
        registry.add_recognizer(recognizer)

    return AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=["fr"],
        default_score_threshold=SCORE_THRESHOLD,
    )
