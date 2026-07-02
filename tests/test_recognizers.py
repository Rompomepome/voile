"""Détection par recognizer + résolution des chevauchements au plus long match.

Données synthétiques uniquement.
"""

from conftest import make_settings
from recognizers import build_analyzer
from surfaces import analyze_text

EMAIL = "jean.dupont@example.org"
NIR_STD = "185057800608491"
NIR_2A = "185052A00404240"
NIR_2B = "290112B12345655"
IBAN_COMPACT = "FR7630006000011234567890189"
IBAN_GROUPE = "FR76 3000 6000 0112 3456 7890 189"
SIREN = "732829320"  # Luhn valide
SIRET = "73282932000033"  # Luhn valide
ADELI = "123456780"  # 9 chiffres, Luhn INVALIDE (sinon classé SIREN)
RPPS = "10001234567"


def detections(analyzer, text):
    """[(type, texte détecté)] triés par position — via le pipeline de prod
    (analyse Presidio + résolution des chevauchements)."""
    results = analyze_text(analyzer, text)
    return [(r.entity_type, text[r.start : r.end]) for r in results]


class TestDetectionSimple:
    def test_email(self, analyzer):
        assert ("EMAIL", EMAIL) in detections(analyzer, f"Contact : {EMAIL} svp")

    def test_telephone_variantes(self, analyzer):
        for phone in [
            "06 12 34 56 78",
            "+33 6 12 34 56 78",
            "+33612345678",
            "06.12.34.56.78",
            "06-12-34-56-78",
            "0612345678",
        ]:
            found = detections(analyzer, f"Rappeler le {phone} demain.")
            assert ("PHONE_FR", phone) in found, phone

    def test_nir_standard(self, analyzer):
        assert ("NIR", NIR_STD) in detections(analyzer, f"NIR : {NIR_STD}.")

    def test_nir_corse_2a(self, analyzer):
        assert ("NIR", NIR_2A) in detections(analyzer, f"Assuré {NIR_2A} (Corse-du-Sud)")

    def test_nir_corse_2b(self, analyzer):
        assert ("NIR", NIR_2B) in detections(analyzer, f"Assurée {NIR_2B} (Haute-Corse)")

    def test_nir_cle_invalide_non_detecte(self, analyzer):
        found = detections(analyzer, "Numéro 185057800608492 douteux")
        assert not any(t == "NIR" for t, _ in found)

    def test_iban_compact(self, analyzer):
        assert ("IBAN_FR", IBAN_COMPACT) in detections(analyzer, f"IBAN {IBAN_COMPACT} ok")

    def test_iban_avec_espaces(self, analyzer):
        assert ("IBAN_FR", IBAN_GROUPE) in detections(analyzer, f"Virement sur {IBAN_GROUPE}.")

    def test_iban_cle_invalide_non_detecte(self, analyzer):
        found = detections(analyzer, "IBAN FR7630006000011234567890188 ?")
        assert not any(t == "IBAN_FR" for t, _ in found)

    def test_rpps(self, analyzer):
        assert ("RPPS", RPPS) in detections(analyzer, f"Dr X, RPPS {RPPS}")

    def test_adeli(self, analyzer):
        assert ("ADELI", ADELI) in detections(analyzer, f"ADELI {ADELI}")

    def test_siren(self, analyzer):
        found = detections(analyzer, f"SIREN {SIREN}")
        assert ("SIREN", SIREN) in found
        # Luhn valide → classé SIREN, pas ADELI (ambiguïté 9 chiffres documentée)
        assert not any(t == "ADELI" for t, _ in found)

    def test_siret(self, analyzer):
        assert ("SIRET", SIRET) in detections(analyzer, f"SIRET {SIRET}")


class TestChevauchements:
    def test_siret_jamais_siren_plus_reste(self, analyzer):
        found = detections(analyzer, f"Établissement {SIRET} enregistré")
        assert found == [("SIRET", SIRET)]

    def test_nir_non_decoupe(self, analyzer):
        # Le NIR (15 chiffres) ne doit pas être découpé par RPPS/ADELI/SIREN/téléphone
        found = detections(analyzer, f"NIR {NIR_STD} enregistré")
        assert found == [("NIR", NIR_STD)]

    def test_nir_corse_non_decoupe(self, analyzer):
        found = detections(analyzer, f"NIR {NIR_2A} enregistré")
        assert found == [("NIR", NIR_2A)]

    def test_iban_compact_non_decoupe(self, analyzer):
        # 25 chiffres contigus après FR : rien d'autre ne doit matcher dedans
        found = detections(analyzer, f"IBAN {IBAN_COMPACT} fin")
        assert found == [("IBAN_FR", IBAN_COMPACT)]


class TestToggles:
    def test_siren_siret_desactives(self):
        analyzer = build_analyzer(make_settings(enable_siren_siret=False))
        found = detections(analyzer, f"SIRET {SIRET} et SIREN {SIREN}")
        assert not any(t in {"SIREN", "SIRET"} for t, _ in found)
        # le 9 chiffres reste détectable comme ADELI (ambiguïté documentée)
        assert ("ADELI", SIREN) in found

    def test_siren_siret_et_adeli_desactives(self):
        analyzer = build_analyzer(
            make_settings(enable_siren_siret=False, enable_adeli=False)
        )
        assert detections(analyzer, f"SIRET {SIRET} et SIREN {SIREN}") == []

    def test_rpps_desactive(self):
        analyzer = build_analyzer(make_settings(enable_rpps=False))
        found = detections(analyzer, f"RPPS {RPPS}")
        assert not any(t == "RPPS" for t, _ in found)

    def test_adeli_desactive(self):
        analyzer = build_analyzer(make_settings(enable_adeli=False))
        found = detections(analyzer, f"ADELI {ADELI}")
        assert not any(t == "ADELI" for t, _ in found)
