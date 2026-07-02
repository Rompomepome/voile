# Build brief v1.1 — Gateway PII « Voile », slice vertical Tier 1

> Brief autonome (ne dépend d'aucun contexte externe). À exécuter par un agent de code.
> v1.1 : couvre le champ `system`, les content blocks, le format de jetons robuste, le comportement streaming, les chevauchements, le cas NIR Corse, la gestion de la clé API.

## Objectif
Proxy local qui s'intercale entre une application et l'API Anthropic : il pseudonymise les identifiants à **format connu** (Tier 1) avant l'envoi, puis ré-identifie la réponse au retour. But du slice = **prouver la boucle de bout en bout**, pas la couverture exhaustive.

## Stack
- Python 3.11+, FastAPI, Uvicorn, `httpx` (timeout configurable, défaut 120 s)
- **Microsoft Presidio** (`presidio-analyzer`, `presidio-anonymizer`) avec `PatternRecognizer` custom pour le Tier 1. Concevoir l'`AnalyzerEngine` pour accueillir plus tard le NER spaCy `fr` (Tier 2) sans refactor.
- Docker

## Périmètre — Tier 1 UNIQUEMENT
Détecter et pseudonymiser :
- Email
- Téléphone FR (`0X XX XX XX XX`, `+33 X…`, avec/sans espaces, points, tirets)
- **NIR** (n° de sécurité sociale, 15 caractères) avec validation **clé modulo 97**.
  ⚠️ **Cas Corse obligatoire** : le NIR peut contenir `2A`/`2B` en position département. Pour le calcul de clé : remplacer `2A`→`19`, `2B`→`18` avant le modulo. Un validateur strictement numérique rejette les NIR corses → faux négatifs qui fuient en clair. Tests unitaires requis sur des NIR synthétiques standard **et** corses.
- **IBAN FR** (validation clé ISO 7064 mod-97, gérer les espaces de groupement)
- **RPPS** (11 chiffres) — activable/désactivable par config
- **ADELI** (9 chiffres) — activable/désactivable
- (option) SIREN (9) / SIRET (14) — activables

**Chevauchements** : résolution au **plus long match** (un SIRET ne doit jamais être détecté comme SIREN + reste ; un NIR ne doit pas être découpé par d'autres patterns). Utiliser la gestion de conflits de Presidio et le vérifier par test.

## Surfaces à scanner (toutes)
1. Le champ **`system`** (string ou liste de blocs) — souvent le plus chargé en PII, ne PAS l'oublier.
2. Chaque message de `messages`, dont `content` peut être :
   - une **string** → scanner directement ;
   - une **liste de blocs** → scanner uniquement les blocs `type: "text"` (champ `text`). Laisser passer les autres types (`image`, `tool_result`…) tels quels en v0.
3. Au retour : ré-identifier les blocs `text` de la réponse.

## Format de jetons (robuste à la génération)
- Format : `<<PII:TYPE:N>>` (ex. `<<PII:EMAIL:1>>`, `<<PII:NIR:2>>`) — délimiteurs improbables, résistants à la reformulation par le modèle.
- **Cohérence intra-requête** : même valeur → même jeton dans toute la requête (system + tous les messages). L'historique complet étant renvoyé à chaque appel, la cohérence intra-requête suffit ; pas de vault persistant en v0.
- **Anti-collision** : si le texte source contient déjà un motif `<<PII:...>>`, l'échapper avant tokenisation et le restaurer après. Test dédié.

## Boucle de bout en bout
1. Endpoint `POST /v1/messages` compatible avec le schéma de l'API Anthropic (passthrough des autres champs : `model`, `max_tokens`, `temperature`, headers `anthropic-version`, etc. — ne rien altérer d'autre).
2. Si `stream: true` → **répondre 400** avec un corps d'erreur explicite (« streaming non supporté en v0 »). Ne pas crasher, ne pas ignorer silencieusement.
3. Scanner les surfaces (§ ci-dessus), détecter (Presidio), tokeniser (réversible, cohérent).
4. Mapping `jeton⇄valeur` **en mémoire, scope requête uniquement**, jamais écrit sur disque ni loggé.
5. Forwarder vers l'upstream. **Clé API** : forwarder le header `x-api-key` du client s'il est présent ; sinon utiliser `ANTHROPIC_API_KEY` de l'env. Erreurs upstream (4xx/5xx) : les transmettre telles quelles à l'appelant.
6. Ré-identifier les blocs `text` de la réponse via le mapping.
7. Renvoyer la réponse ré-identifiée.
8. **Log d'audit** (stdout + fichier optionnel) : horodatage, types de PII détectés, compte par type, latence. **JAMAIS les valeurs, ni le prompt, ni la réponse.** Vérifier aussi que les logs d'accès Uvicorn ne capturent pas les corps de requête.

## Config (env)
- `ANTHROPIC_API_KEY` (fallback si le client n'envoie pas de clé)
- `UPSTREAM_BASE_URL` (défaut `https://api.anthropic.com`)
- `ENABLE_RPPS`, `ENABLE_ADELI`, `ENABLE_SIREN_SIRET` (booléens, défaut `true`)
- `UPSTREAM_TIMEOUT_S` (défaut 120)
- `PORT` (défaut 8080)

## Contraintes (strictes)
- **Pseudonymisation réversible, PAS anonymisation.** Ne rien coder/documenter qui prétende le contraire.
- Le **mapping de ré-identification est l'actif le plus sensible** : en mémoire, éphémère (durée de la requête), jamais loggé.
- **Aucune garantie de capture à 100 %** — le Tier 1 ne couvre que les formats connus. À écrire dans le README.
- Toutes les données de test sont **synthétiques** (NIR/IBAN/RPPS générés avec clés valides, jamais de vraies données).

## Livrables
- App FastAPI (`main.py` + module `recognizers/` + module `tokenizer.py`)
- `Dockerfile` + lancement en une commande
- **Tests** :
  - Unitaires : chaque recognizer (dont NIR corse, IBAN avec espaces, chevauchement SIREN/SIRET)
  - Intégration (upstream mocké) prouvant : (a) l'upstream ne reçoit **que des jetons** (y compris dans `system` et les content blocks), (b) l'appelant récupère les **valeurs réelles**, (c) le log d'audit ne contient **aucune valeur**, (d) `stream: true` → 400 propre, (e) anti-collision jetons
- README quickstart : `docker run …` puis `export ANTHROPIC_BASE_URL=http://localhost:8080`

## Critère d'acceptation (slice validé si)
Un appel via le SDK Anthropic existant, `ANTHROPIC_BASE_URL` pointé sur la gateway, avec des PII dans le `system` **et** dans les messages (formats string et blocs), fonctionne **sans modification du code applicatif** ; l'upstream ne voit prouvablement que des jetons ; l'appelant récupère ses valeurs réelles ; l'audit ne contient aucune valeur.

## Hors scope (ne PAS faire)
- Tier 2 (NER noms/adresses via spaCy)
- Streaming (400 explicite, pas d'implémentation)
- Autres fournisseurs (Bedrock, Mistral, OpenAI)
- Pseudonymisation des blocs `tool_use` / `tool_result` / images
- UI, multi-tenant, persistance du mapping
