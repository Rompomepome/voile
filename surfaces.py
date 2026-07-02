"""Parcours des surfaces à scanner (BRIEF §Surfaces) :

1. le champ ``system`` (string OU liste de blocs) ;
2. chaque message de ``messages`` : ``content`` string OU liste de blocs —
   seuls les blocs ``type: "text"`` sont scannés, les autres (image,
   tool_result, tool_use…) passent tels quels en v0 ;
3. au retour : ré-identification des blocs ``text`` de la réponse.
"""

import copy
from collections import Counter
from functools import partial
from typing import Callable

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from tokenizer import TokenMapper, escape_preexisting_tokens, unescape_tokens

PseudoFn = Callable[[str], str]


def _resolve_conflicts(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Résolution des chevauchements : meilleur score, puis plus long match,
    puis position, puis type (tie-break déterministe). Complète la gestion de
    conflits de Presidio, qui laisse passer deux entités sur le même span
    (ex. SIREN Luhn-valide aussi matché ADELI) — ce qui fausserait l'audit.
    """
    ordered = sorted(
        results,
        key=lambda r: (-r.score, -(r.end - r.start), r.start, r.entity_type),
    )
    kept: list[RecognizerResult] = []
    for result in ordered:
        if all(result.end <= k.start or result.start >= k.end for k in kept):
            kept.append(result)
    return sorted(kept, key=lambda r: r.start)


def analyze_text(analyzer: AnalyzerEngine, text: str) -> list[RecognizerResult]:
    """Détection Tier 1 : analyse Presidio + résolution des chevauchements.
    C'est LE point d'entrée de détection utilisé en production et en test."""
    return _resolve_conflicts(analyzer.analyze(text=text, language="fr"))


def make_pseudonymizer(
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
    mapper: TokenMapper,
    stats: Counter,
) -> PseudoFn:
    """Fabrique la fonction texte→texte tokenisé pour UNE requête.

    L'échappement anti-collision est appliqué avant détection ; la gestion de
    conflits de Presidio (analyzer + anonymizer) résout les chevauchements au
    plus long match / meilleur score.
    """

    def pseudonymize(text: str) -> str:
        text = escape_preexisting_tokens(text)
        results = analyze_text(analyzer, text)
        if not results:
            return text
        for result in results:
            stats[result.entity_type] += 1
        operators = {
            entity_type: OperatorConfig(
                "custom", {"lambda": partial(mapper.token_for, entity_type)}
            )
            for entity_type in {r.entity_type for r in results}
        }
        return anonymizer.anonymize(
            text=text, analyzer_results=results, operators=operators
        ).text

    return pseudonymize


def _process_blocks(blocks: list, fn: PseudoFn) -> None:
    """Applique fn aux blocs type "text" uniquement (in place)."""
    for block in blocks:
        if (
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ):
            block["text"] = fn(block["text"])


def pseudonymize_request(body: dict, fn: PseudoFn) -> dict:
    """Retourne une copie du corps avec toutes les surfaces tokenisées.

    Tous les autres champs (model, max_tokens, temperature…) sont inchangés.
    """
    new_body = copy.deepcopy(body)

    system = new_body.get("system")
    if isinstance(system, str):
        new_body["system"] = fn(system)
    elif isinstance(system, list):
        _process_blocks(system, fn)

    messages = new_body.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = fn(content)
            elif isinstance(content, list):
                _process_blocks(content, fn)

    return new_body


def reidentify_response(data: dict, mapper: TokenMapper) -> dict:
    """Ré-identifie les blocs text de la réponse (in place) :
    détokenisation puis restauration des motifs échappés."""
    content = data.get("content")
    if isinstance(content, list):
        _process_blocks(
            content, lambda text: unescape_tokens(mapper.detokenize(text))
        )
    return data
