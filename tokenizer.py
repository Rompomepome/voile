"""Tokenisation réversible <<PII:TYPE:N>>.

- Cohérence intra-requête : même (type, valeur) → même jeton dans toute la
  requête (system + tous les messages).
- Anti-collision : si le texte source contient déjà un motif ``<<PII:...>>``,
  il est échappé en ``<<PII-RAW:...>>`` avant tokenisation, puis restauré
  après ré-identification de la réponse.
- Le mapping jeton⇄valeur vit UNIQUEMENT en mémoire, à l'échelle d'une
  requête. Il ne doit jamais être loggé, sérialisé ni écrit sur disque.
"""

import re
from collections import defaultdict

TOKEN_RE = re.compile(r"<<PII:[A-Z_]+:\d+>>")

_LITERAL_PREFIX = "<<PII:"
_ESCAPED_PREFIX = "<<PII-RAW:"


def escape_preexisting_tokens(text: str) -> str:
    """Échappe les motifs <<PII:...>> déjà présents dans le texte source."""
    return text.replace(_LITERAL_PREFIX, _ESCAPED_PREFIX)


def unescape_tokens(text: str) -> str:
    """Restaure les motifs échappés (appliqué après détokenisation)."""
    return text.replace(_ESCAPED_PREFIX, _LITERAL_PREFIX)


class TokenMapper:
    """Mapping jeton⇄valeur, scope requête, mémoire uniquement.

    Ne PAS implémenter __repr__/__str__ exposant les valeurs, ne pas logger.
    """

    def __init__(self) -> None:
        self._token_by_value: dict[tuple[str, str], str] = {}
        self._value_by_token: dict[str, str] = {}
        self._counters: defaultdict[str, int] = defaultdict(int)

    def token_for(self, entity_type: str, value: str) -> str:
        key = (entity_type, value)
        token = self._token_by_value.get(key)
        if token is None:
            self._counters[entity_type] += 1
            token = f"<<PII:{entity_type}:{self._counters[entity_type]}>>"
            self._token_by_value[key] = token
            self._value_by_token[token] = value
        return token

    def detokenize(self, text: str) -> str:
        """Remplace nos jetons par les valeurs réelles ; un jeton inconnu
        (halluciné par le modèle) est laissé tel quel."""
        return TOKEN_RE.sub(
            lambda m: self._value_by_token.get(m.group(0), m.group(0)), text
        )

    def __repr__(self) -> str:  # défense : jamais de valeurs dans un repr
        return f"TokenMapper(types={sorted(self._counters)})"
