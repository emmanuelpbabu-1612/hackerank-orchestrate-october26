# SPEC.md — Conventions reverse-engineered from the sample set

Derived from `sample_deletion_requests.csv` (32 cases) + `sample_output.csv` (10 COMPLETE,
22 INCOMPLETE, 0 NOT_APPLICABLE), cross-checked against `dataset/evidence/` contents.
Every convention below is verified by at least the cited sample cases. Open/inferred items
are marked **[inferred]** — no sample covers them.

---

## (a) When each status is chosen

Decision uses **evidence state at `audit_at`**, never `reported_status` (that value is a
claim and is wrong in both directions in the samples).

| Status | Condition at `audit_at` |
|---|---|
| `NOT_APPLICABLE` | `request_text` does **not** authorize deletion (access export, correction, opt-out, "do not close the account"…). Real set contains at least one such case (`case_536`: "I can't access my profile and need help resetting the login. Do not close the account."). **[inferred — no sample covers it]** |
| `COMPLETE` | Deletion authorized and at `audit_at` every relevant record has its policy-mandated treatment and no active flow/restore path can recreate data. |
| `INCOMPLETE` | Deletion authorized and **≥ 1** violation, remaining record, or recreation risk exists at `audit_at`. |

Examples:

1. `case_25` — `reported_status=NOT_STARTED` (claim!) but the freshest evidence ≤
   `audit_at` (`evidence_92`) shows `account_3136` 404, `audit_record_451` retained,
   `analytics_1895` anonymized, `support_2351` redacted, `data_flow_2337` disabled,
   `backup_838` restore-blocked ⇒ **COMPLETE**.
2. `case_05` — `reported_status=COMPLETE` (claim!) but `evidence_54` (failover replica,
   captured 2026-09-02T23:00Z ≤ audit 2026-09-08T13:40Z) still shows `account_005` with
   `account_status=ACTIVE` and full PII ⇒ **INCOMPLETE** (finding + `DELETE_RECORD`).
3. `case_02` — `reported_status=PARTIALLY_COMPLETE`, evidence shows the account gone
   everywhere ⇒ **COMPLETE** with only an `VERIFY_RECORD_ABSENT` step.

---

## (b) Ordering of steps within a phase

Sort key per step (ascending, in priority order):

1. **Operation**, in the exact order of the Allowed-Operations table:
   - FINDING: `REPORT_REMAINING_RECORD` → `REPORT_EXPOSED_PII` → `REPORT_ACTIVE_DATA_FLOW` → `REPORT_RESTORE_RISK`
   - REMEDIATION: `DISABLE_DATA_FLOW` → `BLOCK_RESTORE` → `DELETE_RECORD` → `REDACT_RECORD` → `ANONYMIZE_RECORD`
   - VERIFICATION: `VERIFY_RECORD_ABSENT` → `VERIFY_RECORD_PRESENT` → `VERIFY_RECORD_REDACTED` → `VERIFY_RECORD_ANONYMIZED` → `VERIFY_DATA_FLOW_DISABLED` → `VERIFY_RESTORE_BLOCKED`
2. **`system_id`** ascending **[string sort]**
3. **`resource_id`** ascending **[string sort]**

`step_no` is then assigned consecutively from 1. Phases run FINDING → REMEDIATION →
VERIFICATION as **blocks** (all findings numbered before all remediations, etc.); steps
inside one phase are *not* interleaved with later phases even if a remedy chronologically
precedes a finding-domain action.

Examples:

1. `case_11` findings: `search_052` REMAINING, then `analytics_2034` + `support_864`
   EXPOSED_PII (alphanumeric within same operation), then `data_flow_9522`
   ACTIVE — operation order beats alphabetical order.
2. `case_23` remediation deletes `export_7364` before `search_898` — same operation,
   `export_service` < `search_service`; no dependency re-ordering overrides this.
3. `case_26` verification: account ABSENT (`account_service` < `analytics_platform`…
   alphabetic, op-major), security PRESENT, support REDACTED, analytics ANONYMIZED,
   flow DISABLED, backup BLOCKED — `VERIFY_DATA_FLOW_DISABLED` precedes
   `VERIFY_RESTORE_BLOCKED` because that is the table order (BLOCKED is *last*, not
   alphabetical).

---

## (c) Which evidence is cited per step

Observed facts from all 32 samples:

1. **`evidence_id` is always a `file_id` from `evidence_files.csv`** (e.g. `evidence_54`).
   No sample cites an `activity_id` or `audit_id` **[inferred: follow the sample pattern;
   do not cite activity rows for findings/verifications]**.
2. **FINDING steps and all VERIFICATION steps in COMPLETE cases cite evidence.** All
   REMEDIATION steps and all VERIFICATION steps in INCOMPLETE cases use `""` (118 of the
   193 sample steps are `""`).
3. **Winner rule (verified): the *freshest* eligible evidence file that *proves* the fact.**
   Eligibility = `captured_at <= audit_at` (inclusive; equality accepted). Facts are per
   resource, and each fact cites its *own* winning file:
   - `case_21` (`amara-okeke`): fact exists in `evidence_92` (captured 09-15T11:44:55Z) and
     in the snapshot bundle 2026-09-17 — but the bundle is captured **after** `audit_at`
     (09-15T12:00Z) ⇒ excluded ⇒ `evidence_92` wins.
   - `case_17` (`leonie.g9352`): the fact exists in `resource_lookup_trace_20260310` and
     `service_events_ap_south_20260915` (both ≤ audit_at) ⇒ the **later** capture
     (`evidence_01`) wins.
   - `case_09`: `customer_data_inventory_20260916.sql` (08:37:39 ≤ 09:00) beats the
     `eu_west_20260918` log after audit_at ⇒ `evidence_93` wins for `backup_4978`.
   - `case_31`/`case_32`: `evidence_51` captured **exactly at** audit_at (09-15T12:00:00Z)
     still counts (inclusive boundary).
4. **Facts can be split across files inside one case** (`case_04`: account ABSENT ⇐
   `evidence_54` + analytics ANONYMIZED ⇐ `evidence_56`). Each fact cites the file that
   contains it; if one file contains all case facts, it is reused for every step
   (`case_11`, `case_26`).
5. **`audit_at` is the only time cutoff**: evidence captured after it must not appear,
   even if it would "tell the true story" (case_21 above). Facts the evidence shows at
   earlier captures are treated as still holding at `audit_at` unless a fresher eligible
   file shows otherwise (`case_05`: replica snapshot of 09-02 used for a 09-08 audit).
6. **Never trust claims**: `reported_status` / `reported_result` fields are never cited;
   cases 25/26 (NOT_STARTED → COMPLETE) and 05/10 (COMPLETE → INCOMPLETE) prove both
   directions.

---

## (d) `deletion_rules.csv` → operation/state mapping

Data category `↔ manifest/markdown state tokens observed in evidence
(USER_PROFILE: PRESENT/NOT_FOUND · SEARCH_INDEX_ENTRY: FOUND/… · ANALYTICS_PROFILE:
IDENTIFIABLE/ANONYMIZED · SUPPORT_MESSAGE: IDENTIFIABLE/REDACTED · DATA_FLOW:
ACTIVE/DISABLED · SUPPORT_ATTACHMENT, USER_EXPORT: object present/absent ·
SECURITY_AUDIT_LOG: FOUND + retention_until · BACKUP_ARCHIVE: restore_allowed).

| rule_id | Category → system_id | Bad state ⇒ FINDING op | Remediation | Verification |
|---|---|---|---|---|
| rule_01 | USER_PROFILE → `account_service` (`account_*`) | REMAINING_RECORD/PRESENT | `DELETE_RECORD`/ABSENT | `VERIFY_RECORD_ABSENT` |
| rule_02 | SECONDARY_IDENTIFIER → per case | REMAINING_RECORD | `DELETE_RECORD` | `VERIFY_RECORD_ABSENT` |
| rule_03 | SEARCH_INDEX_ENTRY → `search_service` (`search_*`) | REMAINING_RECORD/PRESENT | `DELETE_RECORD` | `VERIFY_RECORD_ABSENT` |
| rule_04 | CACHE_ENTRY [inferred, not in samples] | REMAINING_RECORD | `DELETE_RECORD` | `VERIFY_RECORD_ABSENT` |
| rule_05 | SUPPORT_MESSAGE → `support_platform` (`support_*`), when shared context ⇒ keep record | EXPOSED_PII/PRESENT | `REDACT_RECORD` | `VERIFY_RECORD_REDACTED` |
| rule_06 | SUPPORT_ATTACHMENT → `support_platform`, subject-only ⇒ delete | REMAINING_RECORD (`case_10` support_002, `case_07` support_001 = identity doc) | `DELETE_RECORD` | `VERIFY_RECORD_ABSENT` |
| rule_07 | ANALYTICS_PROFILE → `analytics_platform` (`analytics_*`) | EXPOSED_PII (IDENTIFIABLE) | `ANONYMIZE_RECORD` | `VERIFY_RECORD_ANONYMIZED` |
| rule_08 | PRODUCT_TELEMETRY [inferred, exposition like rule_07] | EXPOSED_PII | `ANONYMIZE_RECORD` | `VERIFY_RECORD_ANONYMIZED` |
| rule_09 | USER_EXPORT → `export_service` (`export_*`) | REMAINING_RECORD | `DELETE_RECORD` | `VERIFY_RECORD_ABSENT` |
| rule_10 | MARKETING_PROFILE [inferred] | REMAINING_RECORD | `DELETE_RECORD` | `VERIFY_RECORD_ABSENT` |
| rule_11 | EMAIL_DELIVERY_LOG [inferred] | EXPOSED_PII | `REDACT_RECORD` | `VERIFY_RECORD_REDACTED` |
| rule_12 | SECURITY_AUDIT_LOG → `security_service` (`audit_record_*`) | *retention within period* ⇒ RETAIN, never a finding for presence | — | `VERIFY_RECORD_PRESENT/PRESENT` |
| rule_13 | LEGAL_HOLD_RECORD | RETAIN while hold active [not observed in samples] | — | `VERIFY_RECORD_PRESENT` |
| rule_14 | BACKUP_ARCHIVE → `backup_service` (`backup_*`), `restore_allowed=1` | RESTORE_RISK/ACTIVE | `BLOCK_RESTORE` | `VERIFY_RESTORE_BLOCKED` |
| rule_15 | ACCOUNT_TOMBSTONE → `identity_service` (`tombstone_*`) | EXPOSED_PII (PII present while only user_id may stay) | `REDACT_RECORD` | `VERIFY_RECORD_REDACTED` |

Examples (3+): `case_11` rule_03/05/07 + ACTIVE flow; `case_09` rule_14 (backup_4978,
`restore_allowed=1`); `case_31` rule_15 compliant (⇒ `VERIFY_RECORD_REDACTED` only);
`case_32` rule_15 violated (⇒ finding + rem + verify).

---

## (e) Retained records, legal holds, backups

- **Retained records are never "remaining data"**: security-audit records within their
  `retention_until` (e.g. `audit_record_4816`, retention 2032-06-30, audit 2026-10-01) are
  reported only as a *verification* `VERIFY_RECORD_PRESENT`, never a REMAINING finding and
  never remediated (`case_09` step 4, `case_12` step 5, `case_13` step 8). If retention has
  lapsed at `audit_at` the record must be deleted ⇒ extreme case would flip to
  REMAINING + DELETE **[inferred — no sample shows expiry]**.
- **Backups** (`rule_14`) are RETAIN + must have restore access blocked. While
  `restore_allowed=1`, the case is INCOMPLETE with `REPORT_RESTORE_RISK` (state ACTIVE) →
  `BLOCK_RESTORE` → `VERIFY_RESTORE_BLOCKED` (`case_09`, `case_17`, `case_14`). In a
  COMPLETE user the backup already has `restore_allowed=0`; the step is then only
  `VERIFY_RESTORE_BLOCKED` citing evidence (`case_26` step 6). The backup record itself
  must NOT be deleted.
- **Legal holds** [inferred from rule_13 + `legal_retention_register`/`security_extract`
  PDFs]: while a hold is active the affected record(s) are RETAIN ⇒ verify
  `VERIFY_RECORD_PRESENT`; an active hold does not by itself make a case incomplete.
- **Account tombstones** (`rule_15`): the stable `user_id` stays, name/email/phone/hash
  must be gone; compliant tombstone ⇒ `VERIFY_RECORD_REDACTED`; non-compliant ⇒ finding
  `REPORT_EXPOSED_PII`, remediation `REDACT_RECORD`, verification
  `VERIFY_RECORD_REDACTED` (`case_31` vs `case_32`, both via `evidence_51`).

---

## (f) What is verified after remediation / for COMPLETE

- **`INCOMPLETE`** ⇒ verification set = (1) `VERIFY_RECORD_ABSENT` for the *account* even
  when the account was never a finding (`case_06` step 3, `case_09` step 3: primary
  profile already gone stays absent), (2) one verify per remediated/risk resource (exact
  verify op per mapping above), (3) `VERIFY_RECORD_PRESENT` for the security-audit record
  **iff** a retained audit record with `retention_until >= audit_at` exists for the subject
  (absent for users 05–08 ⇒ cases 05–08 have no PRESENT step). Remediations (fiv) always
  have `evidence_id=""`; post-remediation checks cite nothing.
- **`COMPLETE`** ⇒ **only evidence-backed VERIFICATION steps**. One verify per relevant
  resource; the set mirrors exactly the policy-relevant state: ABSENT account (always),
  PRESENT audit record (when it exists and is within retention), REDACTED support
  messages, ANONYMIZED analytics, DISABLED flows, BLOCKED backups (`case_26` =
  all six; `case_21` = only three because the user has no support record, flow, or backup).
  Every such step cites the winning evidence file (§c-noted).
- Typical COMPLETE chain (`case_03`): 3 verification steps all for `evidence_94`
  (resource-lookup trace captured 26T10:38:56 [26T11:00 audit]) showing profile read
  404, audit record retained, analytics record anonymized.

---

## Solver contract (for the build)

1. Identities: resolve requester via `user_identities.email` (case-insensitive) or any
   historical email in `user_audit_log`; record user_id + current/historical
   emails, phones, hashes. Decoy guard: near-name matches (e.g. `Karim El-Masri` vs
   `Amina El-Masri`, `m.rios.gil@...`) must NOT be treated as identity variants.
2. Evidence ingestion: manifest → files; `.sql` executed into per-file SQLite (schema
   shows primary vs failover tables/failover maps such as
   `customer_profiles_failover_replica` vs `..._primary` snapshots; timestamps like
   `2026-09-01T08:37:39Z` define capture scope); JSON bundles, logs, TXT handovers,
   PDFs/images OCR'ed once by VLM (cached by file hash). Compare `primary` and replica
   rows for replication drift facts.
3. Per fact: pattern-map (`REMAINING/PRESENT/FOUND → REMAINING_RECORD`,
   `IDENTIFIABLE → EXPOSED_PII`, `ACTIVE → REPORT_ACTIVE_DATA_FLOW`,
   `restore_allowed=1 → REPORT_RESTORE_RISK`, `REDACTED/ANONYMIZED/DISABLED/restore_allowed=0/
   NOT_FOUND → compliant ⇒ verify-only`).
4. Steps ordered per (b); evidence per (c); `NOT_APPLICABLE` ⇒ `steps_json=[]`.
5. Determinism: no RNG; stable sorting; fixed JSON serialization (compact, keys sorted
   per sample — only array order + key *names* matter to the grader).
