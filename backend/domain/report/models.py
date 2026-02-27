"""
Domain report models: typed dictionaries for pipeline report structures.

These are pure data definitions — no I/O, no external library imports.
"""
from __future__ import annotations

from typing import TypedDict


class IssueRefs(TypedDict, total=False):
    account_id: str | None
    record_id: str | None
    field_path: str | None
    source_lineage: str


class Issue(TypedDict):
    code: str
    severity: str
    stage: str
    message: str
    refs: IssueRefs


class RunFlag(TypedDict):
    id: str
    severity: str
    message: str


class DropDetail(TypedDict, total=False):
    source_file: str | None
    input_path: str | None
    transaction_id: str | None
    record_id: str | None
    drop_reason: str


class MappingDrop(TypedDict, total=False):
    source_file: str
    input_path: str
    transaction_id: str | None
    drop_reason: str
    status: str


class RunMeta(TypedDict):
    run_id: str
    created_at_utc: str
    profile_id: str
    dataset_id: str
    input_dir: str
    adapter_version: str
    sv_schema_version: str
    mapping_version: str
    ruleset_version: str


class Outcome(TypedDict):
    status: str
    stop_reason: str


class SeverityCounts(TypedDict):
    CRITICAL: int
    ERROR: int
    WARN: int
    INFO: int


class StageCounts(TypedDict):
    stage: str
    errors: int
    warnings: int
    infos: int


class SummaryCounts(TypedDict):
    accounts_total: int
    transactions_total: int
    transactions_emitted_sv: int
    transactions_dropped: int
    ml_rows: int
    llm_contexts: int


class Summary(TypedDict):
    counts: SummaryCounts
    by_stage: list[StageCounts]
    by_severity: SeverityCounts


class CollectedRunReport(TypedDict):
    report_schema_version: str
    run: RunMeta
    outcome: Outcome
    summary: Summary
    run_flags: list[RunFlag]
    issues: list[Issue]
    dropped_details: list[DropDetail]
