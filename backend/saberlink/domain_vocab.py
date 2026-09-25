"""Stage A2: a controlled, explainable domain-term vocabulary.

For entity types that expose a structured domain/topic column
(disciplinary_area, application_domains, keywords, main_area, ...), the term
set is just that column's value(s) — already clean, no extraction needed.

NEED has no such column by design (it must not prescribe a solution). For it
(and any other free-text-only field), extract_domain_terms() does a simple
longest-match-first lexical scan against the vocabulary harvested from every
other entity type's structured domain columns. This keeps the domain signal
fully explainable ("matched terms: {...}") instead of an opaque classifier
score — required for the Explicabilidad rubric line.
"""

from __future__ import annotations

import json
import unicodedata

import pandas as pd

from saberlink import config, schema


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def split_terms(value: str) -> list[str]:
    return [t.strip() for t in value.split(";") if t.strip()]


def _field_terms(value, field_name: str, spec: schema.EntitySpec) -> list[str]:
    if value is None or (isinstance(value, float)):
        return []
    text = str(value).strip()
    if not text:
        return []
    if field_name in spec.semicolon_fields:
        return split_terms(text)
    if field_name in spec.space_joined_fields:
        return [text.replace(";", " ").strip()]
    return [text]


def build_vocab(entities: pd.DataFrame) -> set[str]:
    """The term catalog itself, built purely from structured domain fields
    (never from lexical extraction, so this half can't be circular)."""
    vocab: set[str] = set()
    for spec in schema.ENTITY_SPECS.values():
        if not spec.domain_fields:
            continue
        sub = entities[entities.entity_type == spec.entity_type]
        for field_name in spec.domain_fields:
            if field_name not in sub.columns:
                continue
            for value in sub[field_name]:
                vocab.update(_field_terms(value, field_name, spec))
    return vocab


def build_document_frequency(entities: pd.DataFrame, vocab: set[str]) -> dict[str, int]:
    """Document frequency = in how many DISTINCT entities (across the WHOLE
    corpus, every entity type) each vocab term appears as a domain term —
    via structured fields where the entity type has them, or the lexical
    extraction otherwise (safe: it only ever returns terms already in
    `vocab`, computed above, so this is a second, non-circular pass).

    This must scan free-text usage too, not just structured fields: a term
    like "prevención" is genuinely common (used across dozens of unrelated
    NEED/COM/project descriptions) but almost never appears as a literal
    structured keyword tag, so counting structured occurrences alone gave it
    an artificially LOW frequency (looked "rare" -> got a high IDF weight ->
    barely discounted) — the opposite of the intended effect. Counting every
    entity's actual (structured-or-extracted) domain terms is what correctly
    marks generic words as common.
    """
    doc_freq: dict[str, int] = {}
    for entity_id in entities["entity_id"]:
        for term in entity_domain_terms(entity_id, entities, vocab):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    return doc_freq


def save_vocab(vocab: set[str], document_frequency: dict[str, int] | None = None, path=None) -> None:
    path = path or config.DOMAIN_VOCAB_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "terms": sorted(vocab),
        "document_frequency": document_frequency or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_vocab(path=None) -> set[str]:
    path = path or config.DOMAIN_VOCAB_JSON
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):  # backward compatibility with the old flat-list format
        return set(data)
    return set(data["terms"])


def load_term_weights(path=None) -> dict[str, float]:
    """Inverse document-frequency weight per term: rare terms (small df)
    weigh close to 1.0, terms shared by many entities are discounted."""
    path = path or config.DOMAIN_VOCAB_JSON
    data = json.loads(path.read_text(encoding="utf-8"))
    doc_freq = data.get("document_frequency", {}) if isinstance(data, dict) else {}
    if not doc_freq:
        return {}
    max_df = max(doc_freq.values())
    return {term: 1.0 / df if max_df > 1 else 1.0 for term, df in doc_freq.items()}


_folded_terms_cache: dict[int, tuple[int, list[tuple[str, str]]]] = {}


def _sorted_folded_terms(vocab: set[str]) -> list[tuple[str, str]]:
    """(term, folded(term)) pairs, longest-first, computed once per distinct
    vocab object and reused. Folding every vocab term on every
    extract_domain_terms() call (unicode-normalize + strip combining marks,
    per character, per term) was, by measurement, the single biggest cost of
    a live query — this vocabulary is fixed for the lifetime of the process,
    so there is nothing to recompute after the first call."""
    key = id(vocab)
    cached = _folded_terms_cache.get(key)
    if cached is None or cached[0] != len(vocab):
        cached = (len(vocab), [(t, _fold(t)) for t in sorted(vocab, key=len, reverse=True)])
        _folded_terms_cache[key] = cached
    return cached[1]


def extract_domain_terms(text: str, vocab: set[str]) -> set[str]:
    """Longest-match-first substring scan of `text` against `vocab`."""
    if not text:
        return set()
    folded_text = _fold(text)
    found: set[str] = set()
    for term, folded_term in _sorted_folded_terms(vocab):
        if folded_term in folded_text:
            found.add(term)
    return found


def entity_domain_terms(entity_id: str, entities, vocab: set[str]) -> set[str]:
    """Domain term set for one entity: structured columns if the entity type
    has them, otherwise a lexical extraction over its free-text fields.

    `entities` may be the full entities DataFrame (a boolean-mask lookup —
    fine for one-off/test use) or a prebuilt {entity_id: row_dict} lookup
    (see pipeline.py) — the latter is what a live query uses, since a
    per-candidate boolean-mask `.loc` scan over the whole table (thousands
    of times per query) was the dominant cost of a live run_query() call.
    """
    if isinstance(entities, dict):
        row = entities.get(entity_id)
        if row is None:
            return set()
    else:
        matched = entities.loc[entities.entity_id == entity_id]
        if matched.empty:
            return set()
        row = matched.iloc[0]
    entity_type = row["entity_type"]
    spec = schema.ENTITY_SPECS[entity_type]

    if spec.domain_fields:
        terms: set[str] = set()
        for field_name in spec.domain_fields:
            terms.update(_field_terms(row.get(field_name), field_name, spec))
        return terms

    combined_text = " ".join(
        str(row.get(f)) for f in spec.text_fields if not pd.isna(row.get(f))
    )
    return extract_domain_terms(combined_text, vocab)


def run(entities: pd.DataFrame) -> set[str]:
    vocab = build_vocab(entities)
    doc_freq = build_document_frequency(entities, vocab)
    save_vocab(vocab, doc_freq)
    return vocab


if __name__ == "__main__":
    entities = pd.read_parquet(config.ENTITIES_PARQUET)
    vocab = run(entities)
    print(f"domain_vocab: {len(vocab)} terms -> {config.DOMAIN_VOCAB_JSON}")
