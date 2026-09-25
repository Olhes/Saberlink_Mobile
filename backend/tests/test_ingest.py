import hashlib
from pathlib import Path

from saberlink import config, ingest, schema

EXPECTED_COUNTS = {
    "FAC": 6,
    "PRG": 18,
    "GRP": 24,
    "LIN": 60,
    "CAP": 96,
    "SRC": 35,
    "INV": 180,
    "EXP": 720,
    "SUB": 126,
    "COM": 252,
    "LO": 378,
    "NEED": 42,
    "PRJ": 320,
    "THS": 650,
    "PUB": 360,
}


def _hash_raw_data() -> dict[str, str]:
    hashes = {}
    for path in sorted(config.DATA_ROOT.rglob("*")):
        if path.is_file():
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_ingest_never_modifies_raw_data():
    before = _hash_raw_data()
    ingest.run()
    after = _hash_raw_data()
    assert before == after


def test_entity_counts_match_manifest():
    entities, _ = ingest.run()
    counts = entities["entity_type"].value_counts().to_dict()
    assert counts == EXPECTED_COUNTS


def test_bom_stripped_from_id_columns():
    entities, _ = ingest.run()
    fac = entities[entities.entity_type == "FAC"]
    assert set(fac["entity_id"]) == {f"FAC-{i:03d}" for i in range(1, 7)}
    assert "faculty_id" in fac.columns
    assert not any(col.startswith("﻿") for col in entities.columns)


def test_need_originating_faculty_is_inferred_not_authoritative():
    entities, _ = ingest.run()
    needs = entities[entities.entity_type == "NEED"]
    assert needs["originating_faculty_is_inferred"].all()
    assert needs["originating_faculty_id"].str.match(r"FAC-\d{3}").all()


def test_blank_fields_marked_not_available_not_empty_string():
    _, fields_index = ingest.run()
    unavailable = fields_index[fields_index.field_status == "not_available"]
    assert (unavailable["field_text"].isna()).all()


def test_documents_joined_via_catalog():
    _, fields_index = ingest.run()
    md_rows = fields_index[fields_index.field_name == "markdown_doc"]
    assert len(md_rows) == 60
    assert set(md_rows["entity_type"]) <= {"NEED", "PRJ", "THS"}
