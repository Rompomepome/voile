"""Validateurs de clés purs (aucune I/O, aucun log — ne jamais logger les valeurs).

Tous les identifiants traités ici sont des données sensibles : ces fonctions
ne doivent jamais émettre la valeur reçue (exception, log, print).
"""

import re

# Cas Corse : pour le calcul de la clé NIR, le département 2A est remplacé
# par 19 et 2B par 18 avant le modulo 97 (règle officielle NIR).
_NIR_CORSE = {"2A": "19", "2B": "18"}

_SPACES_RE = re.compile(r"\s+")


def validate_nir(nir: str) -> bool:
    """NIR = 13 caractères (numéro) + 2 chiffres (clé), 15 au total.

    Clé = 97 - (numéro mod 97). Le numéro peut contenir 2A/2B en position
    département (index 5-6) : substitution 2A→19, 2B→18 avant le calcul.
    Un validateur strictement numérique rejetterait les NIR corses (faux négatifs).
    """
    nir = nir.strip().upper()
    if len(nir) != 15:
        return False
    number, key = nir[:13], nir[13:]
    if not key.isdigit():
        return False
    dept = number[5:7]
    if dept in _NIR_CORSE:
        number = number[:5] + _NIR_CORSE[dept] + number[7:]
    if not number.isdigit():
        return False
    return int(key) == 97 - (int(number) % 97)


def validate_iban_fr(iban: str) -> bool:
    """IBAN FR : 27 caractères, clé ISO 7064 mod-97. Espaces de groupement tolérés."""
    compact = _SPACES_RE.sub("", iban).upper()
    if len(compact) != 27 or not compact.startswith("FR"):
        return False
    if not compact.isalnum() or not compact[2:4].isdigit():
        return False
    # ISO 7064 : déplacer les 4 premiers caractères à la fin, lettres → 10..35
    rearranged = compact[4:] + compact[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return int(digits) % 97 == 1


def luhn(digits: str) -> bool:
    """Somme de Luhn valide (SIREN, SIRET)."""
    if not digits.isdigit() or not digits:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_siren(siren: str) -> bool:
    return len(siren) == 9 and luhn(siren)


def validate_siret(siret: str) -> bool:
    return len(siret) == 14 and luhn(siret)
