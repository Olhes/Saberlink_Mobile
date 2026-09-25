"""Registry of the 15 Data V1.0 entity types: source file, canonical id column,
free-text fields (embedding units), structured domain fields, and explicit FK
columns. This is the single place that encodes the dataset schema so
ingest.py and graph_build.py never re-derive it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntitySpec:
    entity_type: str
    relative_path: str  # relative to config.DATA_ROOT
    id_col: str
    name_field: str | None  # short display name column, if any
    text_fields: tuple[str, ...]  # columns embedded as (entity_id, field_name) rows
    domain_fields: tuple[str, ...]  # structured domain/topic columns (used as term sets, not embedded)
    semicolon_fields: tuple[str, ...]  # subset of columns that are ';'-delimited lists of phrases
    fk_fields: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (column, target_entity_type)
    # Columns where ';' separates individual WORDS of one phrase, not distinct
    # phrases (confirmed data quirk: research_lines.csv keywords, e.g.
    # "arquitecturas;de;software" means the single phrase "arquitecturas de
    # software" — splitting it as a list would inject stopword fragments
    # like "de" into the domain vocabulary).
    space_joined_fields: tuple[str, ...] = field(default_factory=tuple)


ENTITY_SPECS: dict[str, EntitySpec] = {
    "FAC": EntitySpec(
        entity_type="FAC",
        relative_path="01_institution/faculties.csv",
        id_col="faculty_id",
        name_field="faculty_name",
        text_fields=("description", "strategic_focus"),
        domain_fields=("strategic_focus",),
        semicolon_fields=("strategic_focus",),
        fk_fields=(),
    ),
    "PRG": EntitySpec(
        entity_type="PRG",
        relative_path="01_institution/programs.csv",
        id_col="program_id",
        name_field="program_name",
        text_fields=("description", "graduate_profile", "strategic_topics"),
        domain_fields=("disciplinary_area", "strategic_topics"),
        semicolon_fields=(),
        fk_fields=(("faculty_id", "FAC"),),
    ),
    "GRP": EntitySpec(
        entity_type="GRP",
        relative_path="01_institution/research_groups.csv",
        id_col="group_id",
        name_field="group_name",
        text_fields=("group_name", "description", "mission"),
        domain_fields=("main_area",),
        semicolon_fields=(),
        fk_fields=(("faculty_id", "FAC"),),
    ),
    "LIN": EntitySpec(
        entity_type="LIN",
        relative_path="01_institution/research_lines.csv",
        id_col="line_id",
        name_field="line_name",
        text_fields=("description",),
        domain_fields=("keywords",),
        semicolon_fields=(),
        space_joined_fields=("keywords",),
        fk_fields=(("group_id", "GRP"),),
    ),
    "CAP": EntitySpec(
        entity_type="CAP",
        relative_path="01_institution/institutional_capabilities.csv",
        id_col="capability_id",
        name_field="capability_name",
        text_fields=("capability_name", "description"),
        domain_fields=("application_domains", "available_resources"),
        semicolon_fields=("application_domains", "available_resources"),
        fk_fields=(("responsible_unit", "FAC"),),
    ),
    "SRC": EntitySpec(
        entity_type="SRC",
        relative_path="01_institution/source_catalog.csv",
        id_col="source_id",
        name_field="file_name",
        text_fields=(),  # provenance metadata, not a searchable domain entity
        domain_fields=(),
        semicolon_fields=(),
        fk_fields=(),
    ),
    "INV": EntitySpec(
        entity_type="INV",
        relative_path="02_people_curriculum/researchers.csv",
        id_col="researcher_id",
        name_field="full_name",
        text_fields=(
            "academic_background",
            "profile_summary",
            "research_interests",
            "methodological_expertise",
            "application_domains",
        ),
        domain_fields=("application_domains", "research_interests"),
        semicolon_fields=("research_interests", "methodological_expertise", "application_domains"),
        fk_fields=(("faculty_id", "FAC"), ("primary_program_id", "PRG")),
    ),
    "EXP": EntitySpec(
        entity_type="EXP",
        relative_path="02_people_curriculum/researcher_expertise.csv",
        id_col="expertise_id",
        name_field="expertise_name",
        text_fields=("expertise_name",),
        domain_fields=(),
        semicolon_fields=(),
        fk_fields=(("researcher_id", "INV"),),
    ),
    "SUB": EntitySpec(
        entity_type="SUB",
        relative_path="02_people_curriculum/subjects.csv",
        id_col="subject_id",
        name_field="subject_name",
        text_fields=("description", "purpose", "main_topics"),
        domain_fields=("disciplinary_area", "main_topics"),
        semicolon_fields=(),
        fk_fields=(("program_id", "PRG"),),
    ),
    "COM": EntitySpec(
        entity_type="COM",
        relative_path="02_people_curriculum/competencies.csv",
        id_col="competency_id",
        name_field=None,
        text_fields=("description",),
        domain_fields=(),
        semicolon_fields=(),
        fk_fields=(("program_id", "PRG"), ("subject_id", "SUB")),
    ),
    "LO": EntitySpec(
        entity_type="LO",
        relative_path="02_people_curriculum/learning_outcomes.csv",
        id_col="outcome_id",
        name_field=None,
        text_fields=("outcome_description",),
        domain_fields=(),
        semicolon_fields=(),
        fk_fields=(("subject_id", "SUB"),),
    ),
    "NEED": EntitySpec(
        entity_type="NEED",
        relative_path="03_knowledge_needs/institutional_needs.csv",
        id_col="need_id",
        name_field="title",
        # Deliberately no domain_fields / methodology field: NEED is designed
        # to be solution-agnostic ("sin prescribir una solución tecnológica
        # específica") — domain signal for NEED sources comes only from
        # lexical extraction over these text fields (see domain_vocab.py).
        text_fields=("title", "description", "context", "expected_impact"),
        domain_fields=(),
        semicolon_fields=(),
        fk_fields=(),  # originating_faculty_id is regex-derived, added post-hoc as inferred
    ),
    "PRJ": EntitySpec(
        entity_type="PRJ",
        relative_path="03_knowledge_needs/projects.csv",
        id_col="project_id",
        name_field="title",
        text_fields=(
            "title",
            "problem_statement",
            "abstract",
            "general_objective",
            "methodology",
            "expected_results",
            "application_context",
        ),
        domain_fields=("keywords", "disciplinary_area", "application_context"),
        semicolon_fields=("keywords",),
        fk_fields=(("faculty_id", "FAC"), ("program_id", "PRG"), ("group_id", "GRP")),
    ),
    "THS": EntitySpec(
        entity_type="THS",
        relative_path="03_knowledge_needs/theses.csv",
        id_col="thesis_id",
        name_field="title",
        text_fields=(
            "title",
            "abstract",
            "problem_statement",
            "general_objective",
            "methodology",
            "main_results",
            "conclusions",
        ),
        domain_fields=("keywords", "research_area", "application_context"),
        semicolon_fields=("keywords",),
        fk_fields=(("program_id", "PRG"),),
    ),
    "PUB": EntitySpec(
        entity_type="PUB",
        relative_path="03_knowledge_needs/publications.csv",
        id_col="publication_id",
        name_field="title",
        text_fields=("title", "abstract"),
        domain_fields=("keywords",),
        semicolon_fields=("keywords",),
        fk_fields=(("related_project_id", "PRJ"),),
    ),
}

# Junction/edge tables: (relative_path, from_col, from_type, to_col, to_type, relation_col).
JUNCTION_TABLES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("02_people_curriculum/researcher_group.csv", "researcher_id", "INV", "group_id", "GRP", "role"),
    ("03_knowledge_needs/project_group.csv", "project_id", "PRJ", "group_id", "GRP", "relation"),
    ("03_knowledge_needs/researcher_project.csv", "researcher_id", "INV", "project_id", "PRJ", "role"),
    ("03_knowledge_needs/thesis_advisor.csv", "thesis_id", "THS", "researcher_id", "INV", "role"),
    ("03_knowledge_needs/publication_researcher.csv", "publication_id", "PUB", "researcher_id", "INV", "role"),
    ("03_knowledge_needs/publication_project.csv", "publication_id", "PUB", "project_id", "PRJ", "relation"),
)

DOCUMENT_CATALOG_PATH = "03_knowledge_needs/document_catalog.csv"
DOCUMENTS_SUBDIR = "03_knowledge_needs/documents"

# document_catalog.entity_type values -> canonical entity_type prefix used above.
DOCUMENT_ENTITY_TYPE_MAP = {
    "NEED": "NEED",
    "PROJECT": "PRJ",
    "THESIS": "THS",
}
