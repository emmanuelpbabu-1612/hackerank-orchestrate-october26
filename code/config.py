"""Central configuration and output vocabulary.

WHY a single config module: the challenge contract (AGENTS.md §6.4) fixes the
allowed phase/operation/state vocabulary. Centralizing it keeps every other
module free of magic strings and makes the grader contract auditable.
This module carries NO dataset knowledge (no request ids, no expected labels).
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------- paths
REPO = Path(__file__).resolve().parent.parent
DATASET = REPO / "dataset"
CACHE_DIR = REPO / "code" / ".cache"

# Output CSV contract (exact column order matters to the grader).
OUTPUT_COLUMNS = ["case_id", "deletion_status", "steps_json"]

# Statuses we may emit.
STATUS_COMPLETE = "COMPLETE"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"

# ---------------------------------------------------------------- step vocabulary
PHASES = ["FINDING", "REMEDIATION", "VERIFICATION"]

# Operation order inside each phase (grader sorts by: phase, operation, system_id,
# resource_id). The order below is the order of the Allowed-Operations tables in
# problem_statement.md — NOT alphabetical.
FINDING_OPS = [
    "REPORT_REMAINING_RECORD",
    "REPORT_EXPOSED_PII",
    "REPORT_ACTIVE_DATA_FLOW",
    "REPORT_RESTORE_RISK",
]
REMEDIATION_OPS = [
    "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE",
    "DELETE_RECORD",
    "REDACT_RECORD",
    "ANONYMIZE_RECORD",
]
VERIFY_OPS = [
    "VERIFY_RECORD_ABSENT",
    "VERIFY_RECORD_PRESENT",
    "VERIFY_RECORD_REDACTED",
    "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED",
    "VERIFY_RESTORE_BLOCKED",
]
PHASE_OPS = {
    "FINDING": FINDING_OPS,
    "REMEDIATION": REMEDIATION_OPS,
    "VERIFICATION": VERIFY_OPS,
}

# ---------------------------------------------------------------- LLM configuration
# The deterministic core needs no network. If an API key is present in the env we
# use the configured model to interpret free-text notes / multi-language requests;
# every other code path stays fully deterministic.
MODEL_NAME = os.environ.get("EXORCIST_MODEL", "gpt-4o-mini")  # configurable via env
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")
VLM_API_BASE = os.environ.get("EXORCIST_API_BASE", "https://api.openai.com/v1")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
