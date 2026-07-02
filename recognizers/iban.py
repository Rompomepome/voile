"""IBAN FR (27 caractères) avec validation ISO 7064 mod-97, espaces de groupement tolérés."""

from presidio_analyzer import Pattern, PatternRecognizer

from .validators import validate_iban_fr


class IbanFrRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="iban_fr",
            # FR + 2 chiffres de clé + 23 caractères BBAN (groupes de 4 séparés
            # ou non par des espaces) : 5 groupes de 4 + un groupe final de 3.
            regex=r"(?<![0-9A-Za-z])FR\d{2}(?: ?[0-9A-Za-z]{4}){5} ?[0-9A-Za-z]{3}(?![0-9A-Za-z])",
            score=0.5,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="IBAN_FR",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["iban", "rib", "compte"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return validate_iban_fr(pattern_text)
