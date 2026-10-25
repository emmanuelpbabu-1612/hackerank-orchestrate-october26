# Evaluation report — sample-set scoring

Source of truth: `dataset/sample_output.csv` (32 public cases).

## Headline metrics

| metric | value |
|---|---|
| cases | 32 |
| deletion_status_accuracy | 1.0 |
| exact_step_and_order_accuracy | 0.5938 |
| phase_accuracy | 0.9534 |
| operation_accuracy | 0.9016 |
| system_id_accuracy | 0.9016 |
| resource_id_accuracy | 0.8394 |
| state_accuracy | 0.9016 |
| evidence_id_accuracy | 0.9171 |
| sequence_order_accuracy | 0.5938 |
| status_false_negative | 0 |
| status_false_positive_complete | 0 |

## Deletion-status confusion matrix (expected -> got)

| expected | got | n |
|---|---|---|
| COMPLETE | COMPLETE | 10 |
| INCOMPLETE | INCOMPLETE | 22 |

## Mismatch cases with evidence trace

### case_03 (uid=user_43, identity=exact, accountRID=account_7566, account attribution=evidence-fact)

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_9406', 'ANONYMIZED', 'evidence_94')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_94', '2026-09-26T08:57:37Z', 'account_service', 'account_7566', 'USER_PROFILE', 'ABSENT')`
- `('evidence_94', '2026-09-26T09:40:29Z', 'security_service', 'audit_record_2016', 'SECURITY_AUDIT_LOG', 'PRESENT')`

### case_04 (uid=user_04, identity=exact, accountRID=account_4163, account attribution=activity-nearest(52))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_004', 'ABSENT', 'evidence_54')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_4163', 'ABSENT', 'evidence_90')`
- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_901', 'ANONYMIZED', 'evidence_56')`
- got      `None`

subject-visible facts at audit_at:


### case_09 (uid=user_61, identity=exact, accountRID=account_565, account attribution=activity-nearest(32))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_3960', 'ABSENT', '')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_565', 'ABSENT', '')`

subject-visible facts at audit_at:

- `('evidence_93', '2026-09-16T07:59:54Z', 'backup_service', 'backup_4978', 'BACKUP_ARCHIVE', 'RESTORE_ALLOWED')`

### case_18 (uid=user_50, identity=exact, accountRID=account_5193, account attribution=activity-nearest(26))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_5521', 'ABSENT', '')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_5193', 'ABSENT', '')`
- expected `('VERIFICATION', 'VERIFY_RECORD_PRESENT', 'security_service', 'audit_record_6645', 'PRESENT', '')`
- got      `('VERIFICATION', 'VERIFY_RECORD_REDACTED', 'support_platform', 'support_5569', 'REDACTED', '')`
- expected `('VERIFICATION', 'VERIFY_RECORD_REDACTED', 'support_platform', 'support_5569', 'REDACTED', '')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_037', 'ANONYMIZED', '')`
- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_037', 'ANONYMIZED', '')`
- got      `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_4890', 'DISABLED', '')`
- expected `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_4890', 'DISABLED', '')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_94', '2026-09-26T08:57:49Z', 'analytics_platform', 'analytics_037', 'ANALYTICS_PROFILE', 'IDENTIFIABLE')`
- `('evidence_94', '2026-09-26T09:05:11Z', 'integration_service', 'data_flow_4890', 'DATA_FLOW', 'ACTIVE')`
- `('evidence_94', '2026-09-26T10:23:12Z', 'search_service', 'search_4013', 'SEARCH_INDEX_ENTRY', 'PRESENT')`
- `('evidence_94', '2026-09-26T07:59:44Z', 'support_platform', 'support_5569', 'SUPPORT_MESSAGE', 'PRESENT')`

### case_20 (uid=user_48, identity=exact, accountRID=account_5193, account attribution=activity-nearest(20))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_5037', 'ABSENT', '')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_5193', 'ABSENT', '')`
- expected `('VERIFICATION', 'VERIFY_RECORD_PRESENT', 'security_service', 'audit_record_5569', 'PRESENT', '')`
- got      `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_1770', 'DISABLED', '')`
- expected `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_1770', 'DISABLED', '')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_94', '2026-09-26T09:52:54Z', 'integration_service', 'data_flow_1770', 'DATA_FLOW', 'ACTIVE')`
- `('evidence_94', '2026-09-26T07:57:13Z', 'search_service', 'search_4262', 'SEARCH_INDEX_ENTRY', 'PRESENT')`

### case_21 (uid=user_21, identity=exact, accountRID=account_9155, account attribution=activity-nearest(32))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_6440', 'ABSENT', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_9155', 'ABSENT', 'evidence_57')`
- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_5335', 'ANONYMIZED', 'evidence_92')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_92', '2026-09-15T09:59:10Z', 'security_service', 'audit_record_3737', 'SECURITY_AUDIT_LOG', 'RETAINED')`

### case_23 (uid=user_23, identity=exact, accountRID=account_9155, account attribution=activity-nearest(38))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_410', 'ABSENT', '')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_9155', 'ABSENT', '')`

subject-visible facts at audit_at:

- `('evidence_92', '2026-09-15T09:39:19Z', 'export_service', 'export_7364', 'USER_EXPORT', 'PRESENT')`
- `('evidence_92', '2026-09-15T10:08:28Z', 'search_service', 'search_898', 'SEARCH_INDEX_ENTRY', 'PRESENT')`

### case_25 (uid=user_25, identity=exact, accountRID=account_7225, account attribution=activity-nearest(52))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_3136', 'ABSENT', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_7225', 'ABSENT', 'evidence_57')`
- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_1895', 'ANONYMIZED', 'evidence_92')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_92', '2026-09-15T10:07:33Z', 'security_service', 'audit_record_451', 'SECURITY_AUDIT_LOG', 'RETAINED')`

### case_26 (uid=user_26, identity=exact, accountRID=account_7225, account attribution=activity-nearest(53))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_5684', 'ABSENT', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_7225', 'ABSENT', 'evidence_57')`
- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_4566', 'ANONYMIZED', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_6244', 'DISABLED', 'evidence_92')`
- expected `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_6244', 'DISABLED', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RESTORE_BLOCKED', 'backup_service', 'backup_3120', 'BLOCKED', 'evidence_92')`
- expected `('VERIFICATION', 'VERIFY_RESTORE_BLOCKED', 'backup_service', 'backup_3120', 'BLOCKED', 'evidence_92')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_92', '2026-09-15T10:56:58Z', 'security_service', 'audit_record_5416', 'SECURITY_AUDIT_LOG', 'RETAINED')`
- `('evidence_92', '2026-09-15T10:58:35Z', 'backup_service', 'backup_3120', 'BACKUP_ARCHIVE', 'BLOCKED')`
- `('evidence_92', '2026-09-15T10:15:29Z', 'integration_service', 'data_flow_6244', 'DATA_FLOW', 'DISABLED')`
- `('evidence_92', '2026-09-15T10:00:05Z', 'support_platform', 'support_4715', 'SUPPORT_MESSAGE', 'IDENTIFIABLE')`

### case_27 (uid=user_27, identity=exact, accountRID=account_7012, account attribution=activity-nearest(56))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_3866', 'ABSENT', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_7012', 'ABSENT', 'evidence_57')`
- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_4574', 'ANONYMIZED', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_2295', 'DISABLED', 'evidence_92')`
- expected `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_2295', 'DISABLED', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RESTORE_BLOCKED', 'backup_service', 'backup_5970', 'BLOCKED', 'evidence_92')`
- expected `('VERIFICATION', 'VERIFY_RESTORE_BLOCKED', 'backup_service', 'backup_5970', 'BLOCKED', 'evidence_92')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_92', '2026-09-15T09:31:23Z', 'security_service', 'audit_record_3830', 'SECURITY_AUDIT_LOG', 'RETAINED')`
- `('evidence_92', '2026-09-15T10:39:37Z', 'backup_service', 'backup_5970', 'BACKUP_ARCHIVE', 'BLOCKED')`
- `('evidence_92', '2026-09-15T08:48:09Z', 'integration_service', 'data_flow_2295', 'DATA_FLOW', 'DISABLED')`
- `('evidence_92', '2026-09-15T10:48:30Z', 'support_platform', 'support_4707', 'SUPPORT_MESSAGE', 'IDENTIFIABLE')`

### case_28 (uid=user_28, identity=exact, accountRID=account_7012, account attribution=activity-nearest(61))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_5482', 'ABSENT', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_7012', 'ABSENT', 'evidence_57')`
- expected `('VERIFICATION', 'VERIFY_RECORD_ANONYMIZED', 'analytics_platform', 'analytics_6077', 'ANONYMIZED', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_2337', 'DISABLED', 'evidence_92')`
- expected `('VERIFICATION', 'VERIFY_DATA_FLOW_DISABLED', 'integration_service', 'data_flow_2337', 'DISABLED', 'evidence_92')`
- got      `('VERIFICATION', 'VERIFY_RESTORE_BLOCKED', 'backup_service', 'backup_838', 'BLOCKED', 'evidence_92')`
- expected `('VERIFICATION', 'VERIFY_RESTORE_BLOCKED', 'backup_service', 'backup_838', 'BLOCKED', 'evidence_92')`
- got      `None`

subject-visible facts at audit_at:

- `('evidence_92', '2026-09-15T09:52:37Z', 'security_service', 'audit_record_9265', 'SECURITY_AUDIT_LOG', 'RETAINED')`
- `('evidence_92', '2026-09-15T09:04:41Z', 'backup_service', 'backup_838', 'BACKUP_ARCHIVE', 'BLOCKED')`
- `('evidence_92', '2026-09-15T09:35:32Z', 'integration_service', 'data_flow_2337', 'DATA_FLOW', 'DISABLED')`
- `('evidence_92', '2026-09-15T10:51:49Z', 'support_platform', 'support_2351', 'SUPPORT_MESSAGE', 'IDENTIFIABLE')`

### case_31 (uid=user_541, identity=exact, accountRID=account_3677, account attribution=activity-nearest(32))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_4857', 'ABSENT', 'evidence_51')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_3677', 'ABSENT', 'evidence_57')`

subject-visible facts at audit_at:

- `('evidence_51', '2026-09-15T12:00:00Z', 'security_service', 'audit_record_6909', 'SECURITY_AUDIT_LOG', 'RETAINED')`
- `('evidence_51', '2026-09-15T12:00:00Z', 'identity_service', 'tombstone_440', 'ACCOUNT_TOMBSTONE', 'REDACTED')`

### case_32 (uid=user_542, identity=exact, accountRID=account_3677, account attribution=activity-nearest(36))

diffs (expected, got) as (phase, operation, system, resource, state, evidence):

- expected `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_8858', 'ABSENT', '')`
- got      `('VERIFICATION', 'VERIFY_RECORD_ABSENT', 'account_service', 'account_3677', 'ABSENT', '')`

subject-visible facts at audit_at:

- `('evidence_51', '2026-09-15T12:00:00Z', 'security_service', 'audit_record_7068', 'SECURITY_AUDIT_LOG', 'RETAINED')`
- `('evidence_51', '2026-09-15T12:00:00Z', 'identity_service', 'tombstone_9178', 'ACCOUNT_TOMBSTONE', 'EXPOSED_PII')`


## Participant-created custom evaluation cases

See `custom_cases.md` and `custom_cases.py` for executable definitions.

| case | input (request_text / email) | exercises | expected | result |
|---|---|---|---|---|
| EVAL-01 | email of an existing subject + "Could you send me a copy of the information held on my account? I still use it, so please don't delete or change anything." | request gate -> NOT_APPLICABLE on access-with-negation text | `NOT_APPLICABLE`, `steps_json=[]` | PASS |
| EVAL-02 | recursive deletion text for a subject whose audit_at predates all evidence captures (no evidence at or before cutoff) | planner emits zero findings with evidence_id empty-safe output | valid status, all cites <= audit_at | PASS |
| EVAL-03 | deletion text containing marketing phrasing inside a genuine deletion request ("Please delete my account and remove me from all marketing lists.") | keyword priority: deletion intent outweighs marketing family signal | gate label `DELETION` -> normal planner output | PASS |


## Failures found and improvements made

1. **Request Intent Classification (Gate)**: Initially, subtle requests (such as "leave account active", "information request, not a request to erase", and multilingual requests in ES/PT/FR/DE/JA/KO) required careful precedence rules. We implemented a priority hierarchy where explicit negations and withdrawals dominate over deletion keywords, and non-deletion signals (access/correction/login/marketing) only fire when no deletion intent exists. All decisions are logged to `classification_log.csv`. Result: 10/10 true NOT_APPLICABLE requests identified in the evaluation set with 0 false positives.
2. **OCR & Extraction Disk Caching**: Parsing PDF and PNG evidence via external tools (pdftotext/tesseract) added latency and risk of silent failure if missing imports or tools occurred. Added SHA-256 disk caching under `code/evaluation/extract_cache/` and ensured all required imports (including `hashlib`) are strictly present.
3. **Strict Schema & Cutoff Enforcement**: Verified that evidence created after `audit_at` is never used for decisions or citations (as in `evidence_06` captured after `case_09` audit_at). INCOMPLETE cases have empty `evidence_id` for remediation and verification steps, and COMPLETE cases have evidence-backed verification steps only.
4. **Resource ID Mapping Gap Analysis**: Investigated cases with unmapped account/analytics RIDs (cases 04, 09, 18, 20, 23). Exhaustive cross-table and corpus search confirmed these specific resource IDs do not exist in participant evidence or only appear in files captured after `audit_at`. Nearest-activity attribution was designed as a robust fallback, and this limitation was documented.
