"""Typed loaders for every participant-facing CSV and the evidence manifest.

WHY a dedicated loader: every other module can then assume well-typed rows with
normalized timestamps, and the time contract (`audit_at` cutoff) is enforced in
exactly one place.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from config import DATASET

TS_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"


def parse_ts(value) -> Optional[str]:
    """Normalize a timestamp-like string to the canonical `YYYY-MM-DDTHH:MM:SSZ`.

    WHY lexical compare: canonical Zulu timestamps compare correctly as plain
    strings, which keeps every time filter substring-free and deterministic.
    """
    if value is None:
        return None
    value = str(value).strip()
    m = re.search(TS_PATTERN, value)
    if m:
        return m.group(0)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    return m.group(1) + "T00:00:00Z" if m else None


def ts_ok(event_ts: Optional[str], cutoff: str) -> bool:
    """True when `event_ts` is known and at-or-before the `audit_at` cutoff."""
    return event_ts is not None and event_ts <= cutoff


def load_csv(name: str) -> List[dict]:
    with open(DATASET / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@dataclass
class DeletionRequest:
    case_id: str
    email: str
    requested_at: str
    reported_status: str          # workflow CLAIM — never proof of the true state
    reported_at: str
    audit_at: str                 # the only time cutoff for the answer
    request_text: str
    raw: dict


def load_requests(name: str) -> List[DeletionRequest]:
    out = []
    for row in load_csv(name):
        out.append(DeletionRequest(
            case_id=row["case_id"],
            email=row["email"],
            requested_at=row["requested_at"],
            reported_status=row["reported_status"],
            reported_at=row["reported_at"],
            audit_at=row["audit_at"],
            request_text=row["request_text"],
            raw=row,
        ))
    return out


@dataclass
class EvidenceFile:
    file_id: str
    file_path: str
    origin: str
    captured_at: Optional[str]
    kind: str                     # suffix: sql|json|log|txt|pdf|png


def load_manifest() -> Dict[str, EvidenceFile]:
    out = {}
    for row in load_csv("evidence_files.csv"):
        path = row["file_path"]
        out[row["file_id"]] = EvidenceFile(
            file_id=row["file_id"],
            file_path=path,
            origin=row["origin"],
            captured_at=parse_ts(row["captured_at"]),
            kind=Path_of_suffix(path),
        )
    return out


def Path_of_suffix(path: str) -> str:
    dot = path.rfind(".")
    return path[dot + 1:].lower() if dot >= 0 else ""
