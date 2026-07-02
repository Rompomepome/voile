"""Validateurs de clés — NIR (dont Corse), IBAN FR, Luhn (SIREN/SIRET).

Vecteurs synthétiques, clés calculées (voir BRIEF.md : jamais de vraies données).
"""

from recognizers.validators import (
    luhn,
    validate_iban_fr,
    validate_nir,
    validate_siren,
    validate_siret,
)

# NIR synthétiques valides (clé = 97 - numéro mod 97)
NIR_STD_1 = "185057800608491"
NIR_STD_2 = "290069212345614"
# Cas Corse : clé calculée APRÈS substitution 2A→19 / 2B→18
NIR_2A = "185052A00404240"
NIR_2B = "290112B12345655"


class TestNir:
    def test_standard_valide(self):
        assert validate_nir(NIR_STD_1)
        assert validate_nir(NIR_STD_2)

    def test_standard_cle_fausse(self):
        assert not validate_nir("185057800608492")
        assert not validate_nir("185057800608400")

    def test_corse_2a_valide(self):
        assert validate_nir(NIR_2A)

    def test_corse_2b_valide(self):
        assert validate_nir(NIR_2B)

    def test_corse_minuscule(self):
        assert validate_nir("185052a00404240")

    def test_corse_cle_fausse(self):
        assert not validate_nir("185052A00404241")
        assert not validate_nir("290112B12345656")

    def test_corse_rejete_par_validateur_numerique_naif(self):
        # Le piège documenté dans le brief : un NIR corse n'est pas
        # numérique — un validateur int() strict le rejetterait (faux négatif).
        assert not NIR_2A.isdigit()
        assert validate_nir(NIR_2A)

    def test_lettre_hors_position_departement(self):
        # 2A ailleurs qu'en position département → non numérique → rejet
        assert not validate_nir("1850578006A8491")

    def test_longueur_invalide(self):
        assert not validate_nir("18505780060849")  # 14
        assert not validate_nir("1850578006084911")  # 16
        assert not validate_nir("")

    def test_cle_non_numerique(self):
        assert not validate_nir("1850578006084AB")


class TestIbanFr:
    IBAN_VALIDE = "FR7630006000011234567890189"
    IBAN_GROUPE = "FR76 3000 6000 0112 3456 7890 189"

    def test_compact_valide(self):
        assert validate_iban_fr(self.IBAN_VALIDE)

    def test_avec_espaces_de_groupement(self):
        assert validate_iban_fr(self.IBAN_GROUPE)

    def test_cle_fausse(self):
        assert not validate_iban_fr("FR7630006000011234567890188")

    def test_longueur_fausse(self):
        assert not validate_iban_fr("FR76300060000112345678901")

    def test_pays_non_fr(self):
        assert not validate_iban_fr("DE7630006000011234567890189")

    def test_caracteres_invalides(self):
        assert not validate_iban_fr("FR763000600001123456789018!")


class TestLuhn:
    def test_siren_valide(self):
        assert validate_siren("732829320")

    def test_siren_invalide(self):
        assert not validate_siren("732829321")
        assert not validate_siren("12345678")  # 8 chiffres

    def test_siret_valide(self):
        assert validate_siret("73282932000033")

    def test_siret_invalide(self):
        assert not validate_siret("73282932000034")

    def test_luhn_non_numerique(self):
        assert not luhn("73282932A")
        assert not luhn("")
