"""Stage A1: read Data V1.0 (read-only) into two derived tables:

- entities.parquet: one row per entity across all 15 types, unified/wide
  schema (native columns + entity_id/entity_type/source_file/source_kind).
- fields_index.parquet: one row per (entity_id, field_name) — the unit that
  gets embedded in Stage A3. Includes the 60 documents/*.md files joined via
  document_catalog.csv as an extra `markdown_doc` field per entity.

Never writes into DATA_ROOT. Empty/NaN fields are recorded as
field_status="not_available", never coerced to "" (an empty string would
embed as a near-zero-information vector and spuriously match other empty
fields).
"""

from __future__ import annotations

import re

import pandas as pd

from saberlink import config, schema

FACULTY_ID_RE = re.compile(r"FAC-\d{3}")


def _read_csv(relative_path: str) -> pd.DataFrame:
    path = config.DATA_ROOT / relative_path
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=True)


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, float)) or not str(value).strip()


def build_entities() -> pd.DataFrame:
    """Read every entity CSV into one wide, unified-schema DataFrame."""
    frames = []
    for spec in schema.ENTITY_SPECS.values():
        df = _read_csv(spec.relative_path)
        df["entity_id"] = df[spec.id_col]
        df["entity_type"] = spec.entity_type
        df["source_file"] = spec.relative_path
        df["source_kind"] = "csv_row"
        frames.append(df)

    entities = pd.concat(frames, ignore_index=True, sort=False)

    # Regex-extract the FAC id embedded in institutional_needs.originating_unit.
    # Tagged as inferred: never treated as an authoritative FK (see graph_build.py).
    if "originating_unit" in entities.columns:
        mask = entities["entity_type"] == "NEED"
        extracted = entities.loc[mask, "originating_unit"].fillna("").str.extract(
            f"({FACULTY_ID_RE.pattern})", expand=False
        )
        entities.loc[mask, "originating_faculty_id"] = extracted
        entities["originating_faculty_is_inferred"] = entities["entity_type"] == "NEED"

    return entities


def _document_catalog_rows() -> pd.DataFrame:
    return _read_csv(schema.DOCUMENT_CATALOG_PATH)


def build_fields_index(entities: pd.DataFrame) -> pd.DataFrame:
    """One row per (entity_id, field_name): entity_id, entity_type, field_name,
    field_text, field_status, source_file, source_kind."""
    rows = []
    entities_by_type = {
        etype: sub.set_index("entity_id", drop=False)
        for etype, sub in entities.groupby("entity_type")
    }

    for spec in schema.ENTITY_SPECS.values():
        sub = entities_by_type.get(spec.entity_type)
        if sub is None or not spec.text_fields:
            continue
        for entity_id, row in sub.iterrows():
            for field_name in spec.text_fields:
                value = row.get(field_name)
                if _is_blank(value):
                    rows.append(
                        {
                            "entity_id": entity_id,
                            "entity_type": spec.entity_type,
                            "field_name": field_name,
                            "field_text": None,
                            "field_status": "not_available",
                            "source_file": spec.relative_path,
                            "source_kind": "csv_row",
                        }
                    )
                else:
                    rows.append(
                        {
                            "entity_id": entity_id,
                            "entity_type": spec.entity_type,
                            "field_name": field_name,
                            "field_text": str(value),
                            "field_status": "available",
                            "source_file": spec.relative_path,
                            "source_kind": "csv_row",
                        }
                    )

    # Join documents/*.md via document_catalog.csv.
    catalog = _document_catalog_rows()
    for _, cat_row in catalog.iterrows():
        entity_type = schema.DOCUMENT_ENTITY_TYPE_MAP.get(cat_row["entity_type"])
        if entity_type is None:
            continue
        md_path = config.DOCUMENTS_DIR / cat_row["file_name"]
        text = md_path.read_text(encoding="utf-8").strip()
        rows.append(
            {
                "entity_id": cat_row["entity_id"],
                "entity_type": entity_type,
                "field_name": "markdown_doc",
                "field_text": text if text else None,
                "field_status": "available" if text else "not_available",
                "source_file": f"{schema.DOCUMENTS_SUBDIR}/{cat_row['file_name']}",
                "source_kind": "markdown_doc",
            }
        )

    return pd.DataFrame(rows)


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    entities = build_entities()
    fields_index = build_fields_index(entities)
    entities.to_parquet(config.ENTITIES_PARQUET, index=False)
    fields_index.to_parquet(config.FIELDS_INDEX_PARQUET, index=False)
    return entities, fields_index


if __name__ == "__main__":
    entities, fields_index = run()
    print(f"entities: {len(entities)} rows -> {config.ENTITIES_PARQUET}")
    print(f"fields_index: {len(fields_index)} rows -> {config.FIELDS_INDEX_PARQUET}")
