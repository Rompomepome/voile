"""NIR (numéro de sécurité sociale, 15 caractères) avec validation clé mod 97."""

from presidio_analyzer import Pattern, PatternRecognizer

from .validators import validate_nir


class NirRecognizer(PatternRecognizer):
    """15 caractères contigus : sexe(1) année(2) mois(2) dept(2 ou 2A/2B)
    commune(3) ordre(3) clé(2). La clé est vérifiée (cas Corse inclus)."""

    PATTERNS = [
        Pattern(
            name="nir",
            regex=r"(?<![0-9A-Za-z])[12]\d{4}(?:\d{2}|2[ABab])\d{6}\d{2}(?![0-9A-Za-z])",
            score=0.5,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="NIR",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["nir", "sécurité sociale", "assuré"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return validate_nir(pattern_text)
