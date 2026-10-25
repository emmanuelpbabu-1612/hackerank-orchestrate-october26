# Evaluation harness — 3 participant-created custom cases

These exercise behaviors not covered by the public sample set. They use only
participant-facing data and the pipeline itself (no organizer truth).

| case | input (request_text / email) | exercises | expected |
|---|---|---|---|
| EVAL-01 | email of an existing subject + "Could you send me a copy of the information held on my account? I still use it, so please don't delete or change anything." (variant of case_542) | request gate → NOT_APPLICABLE on access-with-negation text | `NOT_APPLICABLE`, `steps_json=[]` |
| EVAL-02 | recursive deletion text for a subject whose audit_at predates all evidence captures (no evidence at or before the cutoff) | planner must emit zero findings with evidence_id empty-safe output | status `COMPLETE`-or-`INCOMPLETE` with valid steps (per §6.4), no crash, all cites ≤ audit_at |
| EVAL-03 | deletion text containing marketing phrasing inside a genuine deletion request ("Please delete my account and remove me from all marketing lists.") | keyword priority: deletion intent outweighs marketing family signal | gate label `DELETION` → normal planner output |

Run: `python3 code/evaluation/custom_cases.py` (self-checks, prints PASS/FAIL per case).
