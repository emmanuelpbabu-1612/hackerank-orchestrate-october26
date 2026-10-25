"""Participant-created custom evaluation cases (see custom_cases.md).

Self-contained checks that do not touch organizer-only data.
"""
import csv, io, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

import main as agent            # noqa: E402
import classify as gate_mod     # noqa: E402


def main():
    rt = agent.build_runtime()
    agent.rt_texts["texts"] = rt["texts"]
    results = []

    # EVAL-01: access + negation must gate to NOT_APPLICABLE
    label, reason, method = gate_mod.rule_classify(
        "Could you send me a copy of the information held on my account? "
        "I still use it, so please don't delete or change anything.")
    results.append(("EVAL-01", label == "NOT_APPLICABLE", f"{label} ({reason})"))

    # EVAL-02: request whose audit_at precedes every evidence capture
    any_req = dict(list(rt["requests"])[0])
    fake = dict(any_req, case_id="EVAL-02", audit_at="2025-01-01T00:00:00Z",
                requested_at="2024-12-30T00:00:00Z")
    res = agent.report_case(fake, rt["ident"], rt["act"], rt["facts"], rt["manifest"])
    valid_status = res["status"] in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")
    cites_ok = all((s["phase"] == "FINDING" or s["evidence_id"] == "") for s in res["steps"])
    results.append(("EVAL-02", valid_status and cites_ok,
                    f"status={res['status']} steps={len(res['steps'])} cites_ok={cites_ok}"))

    # EVAL-03: deletion text with marketing phrases inside must still gate DELETE
    label, reason, method = gate_mod.rule_classify(
        "Please delete my account and remove me from all marketing lists.")
    results.append(("EVAL-03", label == "DELETION", f"{label} ({reason})"))

    ok = True
    for name, passed, detail in results:
        print(f"{name}: {'PASS' if passed else 'FAIL'} - {detail}")
        ok &= passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
