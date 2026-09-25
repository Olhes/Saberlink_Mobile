"""A plain {entity_id: row_dict} view of entities.parquet.

A live query does thousands of single-entity lookups (domain terms, field
text, record attributes) across the candidate pool. Repeating a boolean-mask
`.loc[entities.entity_id == x]` scan on the full (pyarrow-backed) DataFrame
for each one was, by measurement, the dominant cost of a run_query() call —
tens of seconds for a query scoring ~2000 candidates. A dict built once per
query turns every one of those into an O(1) Python dict lookup.
"""

from __future__ import annotations

import pandas as pd


def build(entities: pd.DataFrame) -> dict[str, dict]:
    return entities.set_index("entity_id", drop=False).to_dict("index")
