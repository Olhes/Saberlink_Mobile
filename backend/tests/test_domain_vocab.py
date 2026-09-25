import pandas as pd

from saberlink import config, domain_vocab as dv, ingest


def test_vocab_has_no_stopword_fragments():
    entities, _ = ingest.run()
    vocab = dv.build_vocab(entities)
    junk = {"el", "en", "y", "de", "del", "la", "los", "las"}
    assert not (vocab & junk)


def test_lin_keywords_reconstructed_as_phrase_not_split_into_words():
    entities, _ = ingest.run()
    vocab = dv.build_vocab(entities)
    # research_lines.csv uses ';' as a word separator within one phrase
    # (e.g. "computacion;en;el;borde" -> "computacion en el borde"), unlike
    # every other file's keyword lists. Splitting it naively would inject
    # stopword fragments like "el"/"en" into the vocabulary.
    assert "aprendizaje automático" in vocab
    assert "computación en el borde" in vocab


def test_need_extracts_domain_terms_from_free_text():
    entities, _ = ingest.run()
    vocab = dv.build_vocab(entities)
    terms = dv.entity_domain_terms("NEED-001", entities, vocab)
    assert "permanencia estudiantil" in terms
    assert "trayectorias educativas" in terms


def test_project_uses_structured_fields_directly():
    entities, _ = ingest.run()
    vocab = dv.build_vocab(entities)
    terms = dv.entity_domain_terms("PRJ-001", entities, vocab)
    assert "permanencia estudiantil" in terms
    assert "trayectorias educativas" in terms
