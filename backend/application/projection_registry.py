"""
Projection registry — single source of truth for all pipeline projections.

Each entry declares a projection's pure function, its associated contract key,
its kind (for Stage 7 FORMAT_FOR_MODEL routing), and whether it needs the
profile dict as input.

Adding a new projection: write the pure function in domain/projections/ and
add one entry below.  No pipeline changes required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from domain.projections.c02_sv_to_ml import project_ml as _project_ml
from domain.projections.c03_sv_to_llm import project_llm as _project_llm
from domain.projections.c05_sv_to_stats import project_stats as _project_stats
from domain.projections.c06_sv_to_monthly_balance import (
    project_monthly_balance as _project_monthly_balance,
)


@dataclass(frozen=True)
class ProjectionSpec:
    name: str
    fn: Callable[..., Any]
    contract_key: str
    kind: Literal["ml", "llm", "generic"]
    needs_profile: bool = False


PROJECTION_REGISTRY: dict[str, ProjectionSpec] = {
    "ml": ProjectionSpec(
        name="ml",
        fn=_project_ml,
        contract_key="C-02",
        kind="ml",
    ),
    "llm": ProjectionSpec(
        name="llm",
        fn=_project_llm,
        contract_key="C-03",
        kind="llm",
        needs_profile=True,
    ),
    "stats": ProjectionSpec(
        name="stats",
        fn=_project_stats,
        contract_key="C-05",
        kind="generic",
    ),
    "monthly_balance": ProjectionSpec(
        name="monthly_balance",
        fn=_project_monthly_balance,
        contract_key="C-06",
        kind="generic",
    ),
}
