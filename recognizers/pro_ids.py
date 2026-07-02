"""Identifiants professionnels : RPPS (11), ADELI (9), SIREN (9), SIRET (14).

Chacun est activable/désactivable par config (voir recognizers/__init__.py).

Ambiguïté assumée (documentée dans le README) : un nombre de 9 chiffres
Luhn-valide est classé SIREN (score validé 1.0 > score ADELI) ; sinon ADELI.
Les lookarounds (?<!\\d)/(?!\\d) empêchent tout sous-match dans une suite de
chiffres plus longue (un SIRET n'est jamais découpé en SIREN + reste, un NIR
n'est jamais découpé par RPPS/ADELI).
"""

from presidio_analyzer import Pattern, PatternRecognizer

from .validators import validate_siren, validate_siret


class RppsRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="rpps",
            regex=r"(?<![0-9A-Za-z])\d{11}(?![0-9A-Za-z])",
            score=0.5,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="RPPS",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["rpps"],
        )


class AdeliRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="adeli",
            regex=r"(?<![0-9A-Za-z])\d{9}(?![0-9A-Za-z])",
            score=0.45,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="ADELI",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["adeli"],
        )


class SirenRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="siren",
            regex=r"(?<![0-9A-Za-z])\d{9}(?![0-9A-Za-z])",
            score=0.5,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="SIREN",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["siren"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return validate_siren(pattern_text)


class SiretRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="siret",
            regex=r"(?<![0-9A-Za-z])\d{14}(?![0-9A-Za-z])",
            score=0.5,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="SIRET",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["siret"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return validate_siret(pattern_text)
