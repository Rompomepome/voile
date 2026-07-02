"""Tier 2 — NER français (PERSON, LOCATION) + ADDRESS pattern.

Le NER est probabiliste : les cas testés ici sont des cas robustes vérifiés
empiriquement sur fr_core_news_lg 3.8.0 (épinglé). Données 100 % synthétiques.
"""

from conftest import make_settings
from recognizers import build_analyzer
from surfaces import analyze_text

EMAIL = "jean.dupont@example.org"
NIR_STD = "185057800608491"


def detections(analyzer, text, threshold=0.4):
    results = analyze_text(analyzer, text, threshold)
    return [(r.entity_type, text[r.start : r.end]) for r in results]


class TestPerson:
    def test_nom_compose(self, analyzer_ner):
        found = detections(
            analyzer_ner, "Le patient Jean-Pierre Lefebvre-Dupont est arrivé."
        )
        assert ("PERSON", "Jean-Pierre Lefebvre-Dupont") in found

    def test_particule_de(self, analyzer_ner):
        found = detections(analyzer_ner, "Rendez-vous avec Amélie de Rochefort demain.")
        assert ("PERSON", "Amélie de Rochefort") in found

    def test_particule_du(self, analyzer_ner):
        found = detections(analyzer_ner, "Bertrand du Plessis a confirmé sa venue.")
        assert ("PERSON", "Bertrand du Plessis") in found

    def test_plusieurs_personnes(self, analyzer_ner):
        found = detections(analyzer_ner, "Marie Dubois et Paul Martin se voient à Lyon.")
        assert ("PERSON", "Marie Dubois") in found
        assert ("PERSON", "Paul Martin") in found
        assert ("LOCATION", "Lyon") in found


class TestFauxPositifs:
    def test_paris_ville_est_location_pas_person_ni_address(self, analyzer_ner):
        found = detections(analyzer_ner, "Je pars à Paris demain matin.")
        assert ("LOCATION", "Paris") in found
        assert not any(t == "PERSON" for t, _ in found)
        assert not any(t == "ADDRESS" for t, _ in found)

    def test_email_jamais_vole_par_le_ner(self, analyzer_ner):
        # fr_core_news_lg tague l'email entier LOC : la priorité
        # pattern > NER doit préserver le type EMAIL
        found = detections(analyzer_ner, f"Contact : {EMAIL}, NIR {NIR_STD}.")
        assert ("EMAIL", EMAIL) in found
        assert ("NIR", NIR_STD) in found
        assert not any(t == "LOCATION" for t, _ in found)


class TestAddress:
    def test_nom_et_adresse_meme_phrase(self, analyzer_ner):
        found = detections(
            analyzer_ner, "Camille Moreau habite 12 rue de la Paix, 75002 Paris."
        )
        assert found == [
            ("PERSON", "Camille Moreau"),
            ("ADDRESS", "12 rue de la Paix"),
            ("ADDRESS", "75002 Paris"),
        ]

    def test_adresse_contenant_un_nom_de_personne(self, analyzer_ner):
        # « Victor Hugo » (PERSON) ne doit pas découper l'adresse
        found = detections(
            analyzer_ner, "L'agence est au 3 bis avenue Victor Hugo, 69003 Lyon."
        )
        assert found == [
            ("ADDRESS", "3 bis avenue Victor Hugo"),
            ("ADDRESS", "69003 Lyon"),
        ]

    def test_particules_et_ville_composee(self, analyzer_ner):
        found = detections(
            analyzer_ner,
            "Adresse : 8 boulevard du Général Leclerc, 13100 Aix-en-Provence.",
        )
        assert ("ADDRESS", "8 boulevard du Général Leclerc") in found
        assert ("ADDRESS", "13100 Aix-en-Provence") in found

    def test_address_sans_ner(self):
        # ADDRESS est un pattern : fonctionne même avec ENABLE_NER=false
        analyzer = build_analyzer(make_settings(enable_address=True))
        found = detections(analyzer, "Livraison au 12 rue de la Paix, 75002 Paris.")
        assert ("ADDRESS", "12 rue de la Paix") in found
        assert ("ADDRESS", "75002 Paris") in found


class TestTogglesEtSeuil:
    def test_ner_desactive_aucun_person_location(self, analyzer):
        # fixture Tier 1 : NER off
        found = detections(analyzer, "Camille Moreau part à Paris.")
        assert found == []

    def test_location_desactivee_person_conserve(self):
        analyzer = build_analyzer(
            make_settings(enable_ner=True, enable_location=False, enable_address=True)
        )
        found = detections(analyzer, "Marie Dubois se rend à Lyon.")
        assert ("PERSON", "Marie Dubois") in found
        assert not any(t == "LOCATION" for t, _ in found)

    def test_address_desactivee(self):
        analyzer = build_analyzer(
            make_settings(enable_ner=True, enable_location=True, enable_address=False)
        )
        found = detections(analyzer, "Livraison au 12 rue de la Paix, 75002 Paris.")
        assert not any(t == "ADDRESS" for t, _ in found)

    def test_seuil_ner_filtre_person_pas_les_patterns(self, analyzer_ner):
        text = f"Camille Moreau, contact {EMAIL}"
        # score NER fixe = 0.85 : un seuil à 0.9 écarte PERSON,
        # les entités pattern (EMAIL) ne sont pas concernées
        strict = detections(analyzer_ner, text, threshold=0.9)
        assert not any(t == "PERSON" for t, _ in strict)
        assert ("EMAIL", EMAIL) in strict

        normal = detections(analyzer_ner, text, threshold=0.4)
        assert ("PERSON", "Camille Moreau") in normal
