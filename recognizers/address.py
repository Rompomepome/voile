"""Adresse postale FR par pattern (complète le NER, qui rate numéros et CP) :

- voie : « 12 rue de la Paix », « 3 bis avenue Victor-Hugo »
- code postal + ville : « 75002 Paris », « 13100 Aix-en-Provence »

Un code postal seul (5 chiffres) n'est PAS détecté : trop de faux positifs
(prix, quantités…). Limite documentée dans le README.
"""

from presidio_analyzer import Pattern, PatternRecognizer

# Majuscule initiale tolérée (« 12 Rue de la Paix ») ; le reste du pattern est
# sensible à la casse (global_regex_flags=0) pour exiger des noms capitalisés.
_VOIE_TYPES = (
    r"(?:[Rr]ue|[Aa]venue|[Aa]v\.|[Bb]oulevard|[Bb]d|[Ii]mpasse|[Aa]ll[ée]e|"
    r"[Pp]lace|[Cc]hemin|[Qq]uai|[Cc]ours|[Rr]oute|[Ss]quare|[Pp]assage|"
    r"[Vv]illa|[Ff]aubourg|[Ff]bg|[Ss]entier|[Hh]ameau|[Ll]ieu-dit)"
)

# Particules minuscules tolérées dans les noms de voie/ville
_PARTICLES = r"(?:de|du|des|d'|d’|la|le|les|l'|l’|en|sur|sous|aux?|et|lès)"

# Mot capitalisé (accents inclus), tirets/apostrophes internes
_CAP_WORD = r"[A-ZÀ-ÖØ-Þ][\w'’-]*"


class AddressRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern(
            name="voie",
            # n° (+ bis/ter) + type de voie + nom (mots capitalisés,
            # particules tolérées entre eux)
            regex=(
                r"(?<![\w])\d{1,4}(?:\s?(?:bis|ter|quater))?,?\s+"
                + _VOIE_TYPES
                + r"(?:\s+" + _PARTICLES + r")*"
                + r"\s+" + _CAP_WORD
                + r"(?:\s+(?:" + _PARTICLES + r"|" + _CAP_WORD + r"))*"
            ),
            score=0.6,
        ),
        Pattern(
            name="cp_ville",
            # code postal (5 chiffres) + ville capitalisée (tirets/particules)
            regex=(
                r"(?<![\dA-Za-z])\d{5}\s+" + _CAP_WORD
                + r"(?:[\s-](?:" + _PARTICLES + r"|" + _CAP_WORD + r"))*"
            ),
            score=0.6,
        ),
    ]

    def __init__(self, supported_language: str = "fr"):
        super().__init__(
            supported_entity="ADDRESS",
            patterns=self.PATTERNS,
            supported_language=supported_language,
            context=["adresse", "domicile", "habite", "résidant"],
            global_regex_flags=0,  # sensible à la casse (noms propres capitalisés)
        )
