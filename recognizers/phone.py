"""Téléphone FR : 0X XX XX XX XX, +33 X…, avec/sans espaces, points, tirets."""

from presidio_analyzer import Pattern, PatternRecognizer


class PhoneFrRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="phone_fr",
            regex=r"(?<![\d+])(?:\+33[\s.\-]?|0)[1-9](?:[\s.\-]?\d{2}){4}(?!\d)",
            score=0.6,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="PHONE_FR",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["téléphone", "tel", "portable", "mobile", "fixe"],
        )
