"""Email — pattern simple, suffisant pour le Tier 1."""

from presidio_analyzer import Pattern, PatternRecognizer


class EmailRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="email",
            regex=r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
            score=0.6,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="EMAIL",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["email", "mail", "courriel"],
        )
