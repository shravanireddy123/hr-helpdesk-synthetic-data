from dataclasses import dataclass

DEFAULT_SEED = 20261022
REFERENCE_DATE = "2026-10-31"  # fixed "today": never use datetime.now()


@dataclass(frozen=True)
class Scale:
    name: str
    departments: int
    employees: int
    policy_documents: int
    knowledge_articles: int
    tickets: int
    messages: int


SCALES = {
    "starter": Scale("starter", 8, 200, 12, 30, 500, 2000),
    "full": Scale("full", 12, 1200, 40, 150, 5000, 20000),
}