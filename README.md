# voile — Gateway PII, slice vertical Tier 1

Proxy local qui s'intercale entre votre application et l'API Anthropic :
il **pseudonymise** les identifiants à format connu (Tier 1) avant l'envoi,
puis **ré-identifie** la réponse au retour. Aucune modification du code
applicatif : il suffit de pointer `ANTHROPIC_BASE_URL` sur la gateway.

> ⚠️ **Pseudonymisation réversible, PAS anonymisation.** Le mapping
> jeton⇄valeur est reconstruit en mémoire à chaque requête et permet la
> ré-identification. Ne présentez jamais ce composant comme un anonymiseur.
>
> ⚠️ **Aucune garantie de capture à 100 %.** Le Tier 1 ne détecte que des
> formats connus (regex + clés). Les noms, adresses, et toute PII sans format
> fixe passent en clair (Tier 2 hors scope de ce slice).

## Quickstart

```bash
docker build -t voile .
docker run --rm -p 8080:8080 -e ANTHROPIC_API_KEY=sk-ant-... voile
```

Puis, côté application (SDK Anthropic inchangé) :

```bash
export ANTHROPIC_BASE_URL=http://localhost:8080
```

Sans Docker :

```bash
pip install -r requirements.txt
python main.py            # ou : uvicorn main:app --port 8080 --no-access-log
```

## Ce qui est détecté (Tier 1)

| Type | Validation | Config |
|---|---|---|
| Email | format | toujours actif |
| Téléphone FR (`0X…`, `+33…`, espaces/points/tirets) | format | toujours actif |
| NIR (15 caractères) | clé mod 97, **cas Corse 2A→19 / 2B→18** | toujours actif |
| IBAN FR (espaces de groupement tolérés) | ISO 7064 mod-97 | toujours actif |
| RPPS (11 chiffres) | format | `ENABLE_RPPS` |
| ADELI (9 chiffres) | format | `ENABLE_ADELI` |
| SIREN (9) / SIRET (14) | Luhn | `ENABLE_SIREN_SIRET` |

Chevauchements résolus au plus long match (un SIRET n'est jamais découpé en
SIREN + reste ; un NIR n'est jamais découpé par d'autres patterns).

Ambiguïté assumée : un nombre de 9 chiffres Luhn-valide est classé SIREN ;
sinon ADELI (si activé). Les NIR sont détectés sous forme contiguë (15
caractères sans séparateurs).

## Surfaces scannées

- le champ `system` (string **ou** liste de blocs) ;
- chaque message : `content` string **ou** liste de blocs — seuls les blocs
  `type: "text"` sont scannés (les blocs `image`, `tool_use`, `tool_result`
  passent tels quels en v0) ;
- au retour : ré-identification des blocs `text` de la réponse.

## Jetons

Format `<<PII:TYPE:N>>` (ex. `<<PII:EMAIL:1>>`). Même valeur → même jeton
dans toute la requête (system + messages). Si le texte source contient déjà
un motif `<<PII:...>>`, il est échappé avant tokenisation et restauré après
(anti-collision testée).

## Config (env)

| Variable | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | fallback si le client n'envoie pas `x-api-key` |
| `UPSTREAM_BASE_URL` | `https://api.anthropic.com` | upstream |
| `ENABLE_RPPS` / `ENABLE_ADELI` / `ENABLE_SIREN_SIRET` | `true` | toggles |
| `UPSTREAM_TIMEOUT_S` | `120` | timeout httpx |
| `PORT` | `8080` | port d'écoute |
| `AUDIT_LOG_FILE` | — | copie du log d'audit dans un fichier |

## Sécurité / limites v0

- Le **mapping jeton⇄valeur est l'actif le plus sensible** : en mémoire,
  scope requête, jamais loggé, jamais écrit sur disque.
- Log d'audit (stdout + fichier optionnel) : horodatage, types détectés,
  compte par type, latence. **Jamais** les valeurs, ni le prompt, ni la
  réponse. Les logs d'accès Uvicorn ne contiennent pas les corps de requête
  (et sont désactivés dans l'image Docker par défense en profondeur).
- `stream: true` → **400** explicite (streaming non supporté en v0).
- Erreurs upstream (4xx/5xx) transmises telles quelles à l'appelant.
- Clé API : header `x-api-key` du client forwardé s'il est présent, sinon
  `ANTHROPIC_API_KEY` de l'environnement.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Toutes les données de test sont **synthétiques** (NIR/IBAN/SIREN/SIRET
générés avec clés valides — jamais de vraies données).

## Extension Tier 2 (hors scope ici)

L'`AnalyzerEngine` Presidio est construit avec un pipeline spaCy `fr` vide :
pour le Tier 2 (NER noms/adresses), remplacer `spacy.blank("fr")` par un
modèle `fr_core_news_*` et ajouter les recognizers NER au registry
(`recognizers/__init__.py`) — sans refactor du reste.
