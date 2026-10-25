#!/usr/bin/env python3
"""Ghost Data Still Exists — deletion-audit agent (deterministic-first).

Pipeline: parse dataset -> facts -> identity resolution -> plan steps -> output CSV.
Modes: --sample (regenerate sample_output), --full (real 518 cases -> output.csv).
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, re, sqlite3, subprocess, sys
from collections import defaultdict
from pathlib import Path
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("classify", Path(__file__).resolve().parent / "classify.py")
_mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
RequestClassifier = _mod.RequestClassifier


REPO = Path(__file__).resolve().parent.parent
DATASET = REPO / "dataset"

TS = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
def parse_ts(v):
    if v is None: return None
    v = str(v).strip()
    m = re.search(rf"({TS})", v)
    if m: return m.group(1)
    m2 = re.search(r"(\d{4}-\d{2}-\d{2})", v)
    return m2.group(1) + "T00:00:00Z" if m2 else None

def ts_ok(t, cut): return t is not None and t <= cut

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
HASH_RE = re.compile(r"\b[0-9a-f]{56}\b|\b[0-9a-f]{64}\b")
UID_RE = re.compile(r"user_\d+\b")

def load_csv(name):
    with open(DATASET / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ============================ categories / output vocabulary =============================
RULES = load_csv("deletion_rules.csv")

CATEGORY_OF_OP = {  # verified against sample_output.csv
  "USER_PROFILE":         ("REPORT_REMAINING_RECORD", "DELETE_RECORD",      "ABSENT",     "VERIFY_RECORD_ABSENT",      "ABSENT"),
  "SECONDARY_IDENTIFIER": ("REPORT_REMAINING_RECORD", "DELETE_RECORD",      "ABSENT",     "VERIFY_RECORD_ABSENT",      "ABSENT"),
  "SEARCH_INDEX_ENTRY":   ("REPORT_REMAINING_RECORD", "DELETE_RECORD",      "ABSENT",     "VERIFY_RECORD_ABSENT",      "ABSENT"),
  "CACHE_ENTRY":          ("REPORT_REMAINING_RECORD", "DELETE_RECORD",      "ABSENT",     "VERIFY_RECORD_ABSENT",      "ABSENT"),
  "USER_EXPORT":          ("REPORT_REMAINING_RECORD", "DELETE_RECORD",      "ABSENT",     "VERIFY_RECORD_ABSENT",      "ABSENT"),
  "MARKETING_PROFILE":    ("REPORT_REMAINING_RECORD", "DELETE_RECORD",      "ABSENT",     "VERIFY_RECORD_ABSENT",      "ABSENT"),
  "SUPPORT_MESSAGE":      ("REPORT_EXPOSED_PII",      "REDACT_RECORD",      "REDACTED",   "VERIFY_RECORD_REDACTED",    "REDACTED"),
  "EMAIL_DELIVERY_LOG":   ("REPORT_EXPOSED_PII",      "REDACT_RECORD",      "REDACTED",   "VERIFY_RECORD_REDACTED",    "REDACTED"),
  "ACCOUNT_TOMBSTONE":    ("REPORT_EXPOSED_PII",      "REDACT_RECORD",      "REDACTED",   "VERIFY_RECORD_REDACTED",    "REDACTED"),
  "SUPPORT_ATTACHMENT":   ("REPORT_REMAINING_RECORD", "DELETE_RECORD",      "ABSENT",     "VERIFY_RECORD_ABSENT",      "ABSENT"),
  "ANALYTICS_PROFILE":    ("REPORT_EXPOSED_PII",      "ANONYMIZE_RECORD",   "ANONYMIZED", "VERIFY_RECORD_ANONYMIZED",  "ANONYMIZED"),
  "PRODUCT_TELEMETRY":    ("REPORT_EXPOSED_PII",      "ANONYMIZE_RECORD",   "ANONYMIZED", "VERIFY_RECORD_ANONYMIZED",  "ANONYMIZED"),
  "SECURITY_AUDIT_LOG":   (None,                      None,                 "RETAINED",   "VERIFY_RECORD_PRESENT",     "PRESENT"),
  "LEGAL_HOLD_RECORD":    (None,                      None,                 "RETAINED",   "VERIFY_RECORD_PRESENT",     "PRESENT"),
  "DATA_FLOW":            ("REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW",  "DISABLED",   "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
  "BACKUP_ARCHIVE":       ("REPORT_RESTORE_RISK",     "BLOCK_RESTORE",      "BLOCKED",    "VERIFY_RESTORE_BLOCKED",    "BLOCKED"),
}
PHASE_ORDER = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
FINDING_OPS  = ["REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK"]
REMEDIATION_OPS = ["DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD"]
VERIFY_OPS   = ["VERIFY_RECORD_ABSENT", "VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED",
                "VERIFY_RECORD_ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED", "VERIFY_RESTORE_BLOCKED"]

def classify(collection, data_store):
    c, s = (collection or "").lower(), (data_store or "").lower()
    if "tombstone" in c or "deleted_customer" in c: return "ACCOUNT_TOMBSTONE"
    if "attachment" in c: return "SUPPORT_ATTACHMENT"
    if "support" in c or "ticket" in c or "conversation" in c: return "SUPPORT_MESSAGE"
    if "search" in c: return "SEARCH_INDEX_ENTRY"
    if "analytics" in c: return "ANALYTICS_PROFILE"
    if "telemetry" in c: return "PRODUCT_TELEMETRY"
    if "marketing" in c: return "MARKETING_PROFILE"
    if "export" in c: return "USER_EXPORT"
    if "connector" in c: return "DATA_FLOW"
    if "backup" in c or "archive" in c: return "BACKUP_ARCHIVE"
    if "legal" in c or "hold" in c: return "LEGAL_HOLD_RECORD"
    if "audit" in c or "security" in c: return "SECURITY_AUDIT_LOG"
    if "cache" in c: return "CACHE_ENTRY"
    if "profile" in c and ("account" in s or "customer_profile" in c): return "USER_PROFILE"
    if "email" in c or "delivery" in c: return "EMAIL_DELIVERY_LOG"
    return None

def map_system(s):
    s = str(s or "").strip().strip('"').lower()
    ALIAS = {
        "search_service": "search_service", "search_index_service": "search_service",
        "account_service": "account_service", "profile_service": "account_service",
        "customer_account_service": "account_service",
        "analytics_platform": "analytics_platform", "analytics_service": "analytics_platform",
        "support_platform": "support_platform", "support_storage_service": "support_platform",
        "support_replica": "support_platform", "attachment_preview": "support_platform",
        "export_service": "export_service",
        "integration_service": "integration_service",
        "backup_service": "backup_service", "backup_restore_service": "backup_service",
        "security_service": "security_service", "compliance_service": "security_service",
        "identity_service": "identity_service", "privacy_treatment_service": "identity_service",
        "legal_service": "legal_service", "legal_register": "legal_service",
        "notification_service": "notification_service", "downstream_delivery_service": "notification_service",
        "email_delivery_service": "email_delivery_service",
        "cache_service": "cache_service",
        "marketing_platform": "marketing_platform", "marketing_service": "marketing_platform",
        "audience_operations": "marketing_platform",
    }
    return ALIAS.get(s, s)

# ============================ facts ================================================
class Fact:
    __slots__ = ("file_id", "ts", "system", "rid", "cat", "refs", "state", "payload")
    def __init__(self, file_id, ts, system, rid, cat, refs, state, payload=None):
        self.file_id, self.ts = file_id, ts
        self.system, self.rid, self.cat = system, rid, cat
        self.refs, self.state, self.payload = set(refs) if refs else set(), state, payload or {}
    def key(self): return (self.system, self.rid, self.cat)
    def __repr__(self):
        return f"<{self.file_id} {self.ts} {self.system}/{self.rid} {self.cat}={self.state} refs={len(self.refs)}>"

def refs_of_record(rec):
    out = set()
    s = str(rec)
    for e in EMAIL_RE.findall(s): out.add(e.lower())
    for h in HASH_RE.findall(s): out.add(h.lower())
    for u in UID_RE.findall(s): out.add(u)
    return out

def subject_refs(rec, keys=("email","owner_email","requester_email","customer_email","lookup_key",
                            "subject_key","email_hash","phone","query","subject_reference",
                            "customer_reference","uploaded_by","user_id","subject_ref",
                            "correlation_key")):
    out = set()
    for k in keys:
        v = rec.get(k)
        if v is None: continue
        v = str(v).strip().strip('"').lower()
        if v and v not in ("none","null","nan"): out.add(v)
    out |= refs_of_record(rec)
    return out

def state_of(cat, rec):
    if cat in ("USER_PROFILE","SEARCH_INDEX_ENTRY","SUPPORT_ATTACHMENT","USER_EXPORT",
               "MARKETING_PROFILE","CACHE_ENTRY","SECONDARY_IDENTIFIER","EMAIL_DELIVERY_LOG"):
        return "PRESENT"
    if cat == "SUPPORT_MESSAGE":
        return "IDENTIFIABLE"
    if cat in ("ANALYTICS_PROFILE","PRODUCT_TELEMETRY"):
        pii = any(rec.get(k) for k in ("email","name","full_name","phone","email_hash","requester_name"))
        return "IDENTIFIABLE" if pii else "ANONYMIZED"
    if cat == "ACCOUNT_TOMBSTONE":
        pii = any(rec.get(k) for k in ("name","full_name","email","phone","email_hash"))
        return "EXPOSED_PII" if pii else "REDACTED"
    if cat == "DATA_FLOW": return "ACTIVE" if rec.get("enabled") in (1,True,"1","true") else "DISABLED"
    if cat == "BACKUP_ARCHIVE": return "RESTORE_ALLOWED" if rec.get("restore_allowed") in (1,True,"1","true") else "BLOCKED"
    if cat in ("SECURITY_AUDIT_LOG","LEGAL_HOLD_RECORD"): return "RETAINED"
    return "PRESENT"

SYSTEM_FOR_TABLE = {
    "customer_profiles": "account_service", "customer_profiles_primary": "account_service",
    "customer_profiles_failover_replica": "account_service",
    "customer_search_documents": "search_service", "search_documents_primary": "search_service",
    "customer_analytics_profiles": "analytics_platform", "customer_analytics_reports": "analytics_platform",
    "support_records": "support_platform", "support_conversations": "support_platform",
    "ticket_attachments": "support_platform",
    "customer_exports": "export_service", "customer_export_jobs": "export_service",
    "connector_subscriptions": "integration_service", "connector_configurations": "integration_service",
    "backup_restore_entries": "backup_service", "backup_catalog": "backup_service",
    "security_audit_records": "security_service", "security_audit_events": "security_service",
    "deleted_customer_references": "identity_service", "customer_references": "identity_service",
    "retained_order_records": "legal_service", "legal_hold_records": "legal_service",
    "operational_record_history": "account_service",
}

def interpret_record_type(tok):
    m = {
        "USER_PROFILE":"USER_PROFILE","ACCOUNT_TOMBSTONE":"ACCOUNT_TOMBSTONE",
        "ANALYTICS_PROFILE":"ANALYTICS_PROFILE","SEARCH_INDEX_ENTRY":"SEARCH_INDEX_ENTRY",
        "SUPPORT_MESSAGE":"SUPPORT_MESSAGE","SUPPORT_ATTACHMENT":"SUPPORT_ATTACHMENT",
        "DATA_FLOW":"DATA_FLOW","USER_EXPORT":"USER_EXPORT","BACKUP_ARCHIVE":"BACKUP_ARCHIVE",
        "SECURITY_AUDIT_LOG":"SECURITY_AUDIT_LOG","LEGAL_HOLD_RECORD":"LEGAL_HOLD_RECORD",
        "EMAIL_DELIVERY_LOG":"EMAIL_DELIVERY_LOG","CACHE_ENTRY":"CACHE_ENTRY",
        "PRODUCT_TELEMETRY":"PRODUCT_TELEMETRY","MARKETING_PROFILE":"MARKETING_PROFILE",
    }
    return m.get(str(tok).upper().strip())

RESULT_STATE = {  # record_lookup result / handover STATE tokens
  "FOUND": "PRESENT", "NOT_FOUND": "ABSENT", "IDENTIFIABLE": "IDENTIFIABLE",
  "REDACTED": "REDACTED", "ANONYMIZED": "ANONYMIZED", "ACTIVE": "ACTIVE", "DISABLED": "DISABLED",
  "BLOCKED": "BLOCKED", "RETAINED": "RETAINED", "DELETED": "ABSENT",
}


def infer_system_by_rid(rid):
    p = (rid or "").split("_")[0]
    return {"search": "search_service", "account": "account_service", "analytics": "analytics_platform",
            "support": "support_platform", "export": "export_service", "backup": "backup_service",
            "audit": "security_service", "tombstone": "identity_service", "data": "integration_service",
            "object": "object_storage", "marketing": "marketing_platform", "cache": "cache_service",
            "email": "notification_service", "legal": "legal_service"}.get(p, p)

# trace_id correlation: merge started-line refs into matched completed rows per file
def correlate_traces(raw_lines, facts):
    pass

def parse_manifest():
    out = {}
    for r in load_csv("evidence_files.csv"):
        out[r["file_id"]] = {"file_id": r["file_id"], "path": r["file_path"], "origin": r["origin"],
                             "captured_at": parse_ts(r["captured_at"]),
                             "kind": Path(r["file_path"]).suffix[1:]}
    return out

def sql_facts(f):
    p = str(DATASET / f["path"])
    db = sqlite3.connect(":memory:"); db.executescript(open(p, encoding="utf-8").read())
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    facts = []
    for t in tables:
        if t == "snapshot_scope": continue
        cols = [r[1] for r in db.execute(f"PRAGMA table_info({t})")]
        if not cols: continue
        base_system = SYSTEM_FOR_TABLE.get(t)
        for row in db.execute(f"SELECT * FROM {t}"):
            rec = dict(zip(cols, row))
            if isinstance(rec.get("record_json"), str):   # primary/replica/failover one-table shapes
                try: payload = json.loads(rec["record_json"])
                except Exception: continue
                coll = (rec.get("collection_name") or "").lower()
                sysid = map_system(rec.get("origin_system"))
                cat = classify(coll, sysid)
                if sysid == "legal_service" or "retained_order" in coll: cat = "LEGAL_HOLD_RECORD"
                rid = payload.get("resource_id") or rec.get("resource_id")
                at = parse_ts(rec.get("updated_at")) or f["captured_at"]
                refs = subject_refs(payload) | subject_refs(rec) | refs_of_record(payload)
                refs.add(str(rec.get("subject_reference", "")).lower())
                refs.discard(""); refs.discard("none")
                st = state_of(cat, payload)
                if rid:
                    facts.append(Fact(f["file_id"], at, sysid, rid, cat, refs, st,
                                      dict(payload, collection=coll)))
                continue
            sysid = base_system or "unknown"
            cat = classify(t, sysid)
            rid = rec.get("resource_id")
            if not rid: continue
            at = parse_ts(rec.get("updated_at") or rec.get("recorded_at") or rec.get("indexed_at")) or f["captured_at"]
            payload = dict(rec); payload["collection"] = t
            refs = subject_refs(rec) | refs_of_record(rec)
            st = state_of(cat, rec)
            if t == "security_audit_records":
                refs.add((rec.get("subject_reference") or "").lower())
                payload["retention_until"] = rec.get("retention_until")
            if t in ("support_records","customer_exports","customer_search_documents","connector_subscriptions",
                     "backup_restore_entries","customer_analytics_profiles"):
                pass
            refs = {x for x in refs if x and x not in ("none","null")}
            facts.append(Fact(f["file_id"], at, sysid, rid, cat, refs, st, payload))
    return facts

def json_facts(f):
    d = json.load(open(DATASET / f["path"], encoding="utf-8"))
    facts = []
    top_at = parse_ts(d.get("exported_at") or d.get("captured_at"))
    def ingest(r, system, coll, at, grp=None):
        rid = r.get("resource_id")
        if not rid: return
        cat = classify(coll if isinstance(coll, str) else (grp or ""), system)
        if grp:
            cat = {"profile_lookups":"USER_PROFILE","profiles":"ANALYTICS_PROFILE","restore_entries":"BACKUP_ARCHIVE",
                   "exports":"USER_EXPORT","connectors":"DATA_FLOW","index_queries":"SEARCH_INDEX_ENTRY",
                   "audit_records":"SECURITY_AUDIT_LOG","tickets":"SUPPORT_MESSAGE"}.get(grp, cat)
        payload = dict(r); payload["collection"] = coll if isinstance(coll, str) else ""
        refs = subject_refs(r) | refs_of_record(r)
        system = system or infer_system_by_rid(rid)
        if system == "unknown": system = infer_system_by_rid(rid)
        st = None
        if grp == "index_queries":
            docs = ((r.get("hits") or {}).get("documents") or [])
            for doc in docs: refs |= subject_refs(doc)
            st = "PRESENT" if docs else ("ABSENT" if (r.get("hits") or {}).get("total", 0) == 0 else "PRESENT")
        elif grp == "profile_lookups":
            prof = r.get("profile")
            refs |= subject_refs(prof or {})
            st = "ABSENT" if (prof is None or r.get("status_code") == 404) else "PRESENT"
        if st is None:
            st = state_of(cat, r)
        if cat == "SECURITY_AUDIT_LOG" and r.get("retention_until"):
            payload["retention_until"] = r["retention_until"]
        facts.append(Fact(f["file_id"], at, map_system(system), rid, cat, refs, st, payload))
    if "snapshots" in d:
        for snap in d["snapshots"]:
            at = parse_ts(snap.get("captured_at")) or top_at
            system = map_system(snap.get("data_store"))
            for r in snap.get("records") or []:
                if "record_type" in r and "result" in r:
                    typed_or_lookup(f, r, at, facts, system_given=snap.get("data_store"))
                    continue
                if "record_type" in r:
                    typed_or_lookup(f, r, at, facts, system_given=system)
                    continue
                ingest(r, system, snap.get("collection"), at)
    elif "service_exports" in d:
        for system, groups in d["service_exports"].items():
            for grp, recs in groups.items():
                for r in recs or []:
                    at = parse_ts(r.get("observed_at")) or top_at
                    if "record_type" in r:
                        typed_or_lookup(f, r, at, facts, system_given=system, grp=grp)
                        continue
                    ingest(r, system, grp, at, grp=grp)
    elif "records" in d:
        for r in d["records"]:
            at = parse_ts(r.get("captured_at") or r.get("recorded_at")) or top_at
            if "record_type" in r:
                typed_or_lookup(f, r, at, facts, system_given=r.get("system"))
                continue
            at = parse_ts(r.get("uploaded_at")) or at
            ingest(r, map_system(r.get("system") or r.get("data_store") or ""),
                   r.get("collection") or guess_cat(r), at)
    return facts

def guess_cat(r):
    s = json.dumps(r).lower()
    for kw, cat in (("search","SEARCH_INDEX_ENTRY"),("analytics","ANALYTICS_PROFILE"),("ticket","SUPPORT_MESSAGE"),
                    ("conversation","SUPPORT_MESSAGE"),("backup","BACKUP_ARCHIVE"),("export","USER_EXPORT"),
                    ("connector","DATA_FLOW"),("audit","SECURITY_AUDIT_LOG"),("tombstone","ACCOUNT_TOMBSTONE"),
                    ("attachment","SUPPORT_ATTACHMENT"),("marketing","MARKETING_PROFILE"),
                    ("telemetry","PRODUCT_TELEMETRY"),("legal","LEGAL_HOLD_RECORD"),("hold","LEGAL_HOLD_RECORD"),
                    ("email","EMAIL_DELIVERY_LOG"),("cache","CACHE_ENTRY")):
        if kw in s: return cat
    return None

def typed_or_lookup(f, r, at, facts, system_given=None, grp=None, extra_refs=None):
    rid = r.get("resource_id")
    if not rid: return
    cat = interpret_record_type(r.get("record_type") or r.get("result")) or classify((r.get("collection") or "").lower() or (grp or ""), map_system(system_given) if system_given else "")
    resulttok = str(r.get("result") or r.get("state") or "").upper()
    lookups_like = "record_lookup" in str(r.get("record_type")) or (r.get("result") and r.get("record_type"))
    refs = subject_refs(r) | refs_of_record(r) | (extra_refs or set())
    if resulttok in RESULT_STATE:
        st = RESULT_STATE[resulttok]
        facts.append(Fact(f["file_id"], at, map_system(system_given) if system_given else infer_system_by_rid(rid),
                          rid, cat, refs, st, dict(r, collection=grp or "")))
        return
    st = state_of(cat, r)
    facts.append(Fact(f["file_id"], at, map_system(system_given) if system_given else infer_system_by_rid(rid),
                      rid, cat, refs, st, dict(r, collection=grp or "")))

def text_facts(f):
    txt = open(DATASET / f["path"], encoding="utf-8", errors="ignore").read()
    facts = []
    lines = txt.splitlines()
    # pass 1: trace correlation — refs carried by *started* rows
    trace_refs = defaultdict(set)
    trace_kv = {}
    for line in lines:
        if "trace_id" not in line: continue
        m = re.search(r"\{.*\}", line)
        if m:
            try: attrs = json.loads(m.group(0))
            except Exception: attrs = None
            kv = attrs if isinstance(attrs, dict) else dict((mm[0], mm[1]) for mm in
                                                            re.findall(r'(\w+)=(".*?"|\S+)', line))
        else:
            kv = dict((mm[0], mm[1]) for mm in re.findall(r'(\w+)=(".*?"|\S+)', line))
        ev = str(kv.get("event", ""))
        tid = str(kv.get("trace_id", "")).strip('"')
        if not tid: continue
        if ev.endswith("_started") or ev.endswith("_acquired"):
            trace_kv[tid] = {k: str(v).strip('"') for k, v in kv.items()
                             if k not in ("event", "trace_id", "severity", "logger", "service",
                                          "instance", "pod", "region")}
            trace_refs[tid] |= subject_refs(kv) | refs_of_record(line)
    for line in lines:
        if not line.strip(): continue
        at = parse_ts(line)
        if at is None: continue
        # handover rows: "- ts | system | rid | CATEGORY | STATE | subject"
        m = re.match(rf"-\s*({TS})\s*\|\s*([a-z_]+)\s*\|\s*(\w+)\s*\|\s*([A-Z_]+)\s*\|\s*([A-Z_]+)\s*\|\s*(.*?)\s*$", line)
        if m:
            ts, sysid, rid, rtok, stok, sub = m.groups()
            cat = interpret_record_type(rtok)
            if not cat: continue
            refs = subject_refs({"subject_reference": sub}) | refs_of_record(sub)
            facts.append(Fact(f["file_id"], ts, map_system(sysid), rid, cat, refs,
                              RESULT_STATE.get(stok, "PRESENT"), {"line": line[:400]}))
            continue
        # JSON-per-line
        m = re.search(r"\{.*\}", line)
        if m:
            try: attrs = json.loads(m.group(0))
            except Exception: attrs = None
            if isinstance(attrs, dict):
                emit_structured(f, attrs, at, line, facts, trace_refs, trace_kv)
                continue
        # key=value
        kv = dict((mm[0], mm[1]) for mm in
                  re.findall(r'(\w+)=(".*?"|\S+)', line))
        ev = kv.get("event", "")
        # contact lookups that resolve a row: a contact record keyed by identifier -> DELETE (rule_02)
        if ev == "contact_lookup_completed":
            try: nrows = int(str(kv.get("rows", "0")).strip('"'))
            except ValueError: nrows = 0
            if nrows >= 1:
                svc = map_system(kv.get("system") or kv.get("service")) or infer_system_by_rid(kv.get("resource_id", ""))
                refs = subject_refs(kv) | refs_of_record(line) | trace_refs.get(str(kv.get("trace_id", "")).strip('"'), set())
                facts.append(Fact(f["file_id"], at, svc, kv.get("resource_id", "").strip('"'),
                                  "SECONDARY_IDENTIFIER", refs, "PRESENT", {"line": line[:400], **kv}))
            continue
        if "record_lookup" in ev or ("record_type" in kv and "result" in kv):
            rr = {k: kv.get(k, "").strip('"') for k in
                  ("system", "resource_id", "record_type", "result", "subject_reference", "subject_key", "lookup_key")}
            rr = {k: v for k, v in rr.items() if v != ""}
            typed_or_lookup(f, {"resource_id": rr.get("resource_id"), "record_type": rr.get("record_type"),
                                "result": rr.get("result"), "subject_reference": rr.get("subject_reference")
                                or rr.get("subject_key") or rr.get("lookup_key")},
                            at, facts, system_given=rr.get("system"), extra_refs=trace_refs.get(str(kv.get("trace_id", "")).strip('"'), set()))
            continue
        rid = kv.get("resource_id", "").strip('"')
        if not rid: continue
        ev_tok = kv.get("event", "")
        if ev_tok.endswith("_started") or ev_tok.endswith("_acquired"):
            continue                       # in-flight trace rows prove no state
        svc = map_system(kv.get("system") or kv.get("service"))
        cat = interpret_record_type(kv.get("record_type")) or interpret_record_type("") or classify_guess_kv(kv, line)
        st = serve_state_from_line(cat, line, kv)
        refs = subject_refs(kv) | refs_of_record(line) | trace_refs.get(str(kv.get("trace_id", "")).strip('"'), set())
        tid = str(kv.get("trace_id", "")).strip('"')
        payload = {"line": line[:400], **kv}
        if tid in trace_kv:
            payload["trace_kv"] = trace_kv[tid]
        if rid and cat:
            if not svc: svc = infer_system_by_rid(rid)
            facts.append(Fact(f["file_id"], at, svc, rid, cat, refs, st, payload))
    return facts

def classify_guess_kv(kv, line):
    # infer by resource prefix when type token is absent
    rid = kv.get("resource_id", "")
    prefix = rid.split("_")[0] if rid else ""
    pref = {"search":"SEARCH_INDEX_ENTRY","analytics":"ANALYTICS_PROFILE","support":"SUPPORT_MESSAGE",
            "export":"USER_EXPORT","backup":"BACKUP_ARCHIVE","audit_record":"SECURITY_AUDIT_LOG",
            "tombstone":"ACCOUNT_TOMBSTONE","data_flow":"DATA_FLOW","connector":"DATA_FLOW",
            "account":"USER_PROFILE","cache":"CACHE_ENTRY","telemetry":"PRODUCT_TELEMETRY",
            "marketing":"MARKETING_PROFILE","legal":"LEGAL_HOLD_RECORD","email_delivery":"EMAIL_DELIVERY_LOG"}
    cat = pref.get(prefix)
    if cat: return cat
    return classify((kv.get("event", "") + " " + line[:200]).lower(), map_system(kv.get("service")))

def emit_structured(f, attrs, at, line, facts, trace_refs=None, trace_kv=None):
    rid = attrs.get("resource_id")
    if not rid: return
    if str(attrs.get("event", "")).endswith("_started"): return
    trace_refs = trace_refs or {}
    trace_kv = trace_kv or {}
    svc = map_system(attrs.get("service") or attrs.get("logger"))
    ev = str(attrs.get("event",""))
    if "record_lookup" in ev:
        typed_or_lookup(f, {"resource_id": rid, "record_type": attrs.get("record_type"),
                            "result": attrs.get("result"),
                            "subject_reference": attrs.get("subject_reference") or attrs.get("subject_key")
                            or attrs.get("lookup_key")},
                        at, facts, system_given=attrs.get("system"))
        return
    cat = interpret_record_type(attrs.get("record_type")) or classify_guess_kv(attrs, line)
    st = serve_state_from_line(cat, line, attrs)
    tid = str(attrs.get("trace_id", "")).strip('"')
    refs = subject_refs(attrs) | refs_of_record(line) | trace_refs.get(tid, set())
    payload = dict(attrs, line=line[:400])
    if tid in trace_kv:
        payload["trace_kv"] = trace_kv[tid]
    if cat:
        facts.append(Fact(f["file_id"], at, svc, rid, cat, refs, st, payload))

def serve_state_from_line(cat, line, kv=None):
    tl = line.lower()
    kv = kv or {}
    def nonull(k):
        v = kv.get(k)
        return v is not None and str(v).strip('"').lower() not in ("", "none", "null", "nan")
    if cat == "USER_PROFILE":
        if "not_found" in tl or 'rows="0"' in line or "rows=0" in line or '"http_status":"404"' in line: return "ABSENT"
        return "PRESENT"
    if cat == "SEARCH_INDEX_ENTRY":
        if "result=hit" in tl or '"result":"hit"' in line: return "PRESENT"
        if "no_hit" in tl or "total_hits=0" in line or '"total":0' in line: return "ABSENT"
        return "PRESENT" if "hit" in tl else "ABSENT"
    if cat in ("SUPPORT_MESSAGE","SUPPORT_ATTACHMENT"):
        if "redacted" in tl: return "REDACTED"
        if "identifiable" in tl: return "IDENTIFIABLE"
        return "PRESENT"
    if cat in ("ANALYTICS_PROFILE","ACCOUNT_TOMBSTONE"):
        if "anonymized" in tl: return "ANONYMIZED"
        # identifier detections: matched_value / direct_identifiers / any field value
        if "matched_value=" in line or '"matched_value"' in line: return "IDENTIFIABLE"
        if "direct_identifiers=0" not in tl and "direct_identifiers=" in tl:
            return "IDENTIFIABLE" if "direct_identifiers=0" not in tl else "ANONYMIZED"
        if cat == "ANALYTICS_PROFILE" and any(nonull(k) for k in
                ("email", "email_hash", "phone", "customer_reference", "name", "full_name")):
            return "IDENTIFIABLE"
        if cat == "ACCOUNT_TOMBSTONE" and any(nonull(k) for k in
                ("email", "email_hash", "phone", "name", "full_name")):
            return "EXPOSED_PII"
        if "identifiable" in tl or "exposed" in tl or "pii" in tl: return "IDENTIFIABLE"
        return "ANONYMIZED"
    if cat == "DATA_FLOW":
        if "enabled=false" in tl or '"enabled": false' in line or "disabled" in tl: return "DISABLED"
        if "enabled=true" in tl or '"enabled": true' in line: return "ACTIVE"
        return "ACTIVE" if "enabled" in tl else "DISABLED"
    if cat == "BACKUP_ARCHIVE":
        if "restore_allowed=false" in tl or '"restore_allowed": false' in line or "restore_allowed=0" in tl: return "BLOCKED"
        if "restore_allowed=true" in tl or '"restore_allowed": true' in line or "restore_allowed=1" in tl: return "RESTORE_ALLOWED"
        return "RESTORE_ALLOWED" if "restore" in tl else "BLOCKED"
    return "PRESENT"

def tool_extract(cmd, f):
    """Run an external extraction tool with a disk cache keyed by the file hash.

    Returns the extracted text (or "" when the tool is unavailable)."""
    cache_dir = REPO / "code" / "evaluation" / "extract_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256((DATASET / f["path"]).read_bytes()).hexdigest()
    cpath = cache_dir / f"{f['file_id']}_{h[:16]}.txt"
    if cpath.exists():
        return cpath.read_text(encoding="utf-8")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        txt = r.stdout or ""
    except FileNotFoundError:
        txt = ""
    cpath.write_text(txt, encoding="utf-8")
    return txt

def pdf_facts(f):
    txt = tool_extract(["pdftotext", str(DATASET / f["path"]), "-"], f)
    facts, meta = [], {"text": txt}
    att = re.search(r"Support reference\s+([\w\-]+)\s*/\s*(\w+)", txt)
    if att:
        rid = att.group(2)
        mails = {e.lower() for e in EMAIL_RE.findall(txt)}
        facts.append(Fact(f["file_id"], f["captured_at"], "support_platform", rid, "SUPPORT_ATTACHMENT",
                          mails | refs_of_record(txt), "PRESENT", meta))
    for line in txt.splitlines():
        line = line.strip()
        m = re.match(r"^\d+\s+(\S+)\s*\|\s*(user_\d+)\s*\|", line)
        if m:
            rid, uid = m.groups()
            facts.append(Fact(f["file_id"], f["captured_at"], "legal_service", rid, "LEGAL_HOLD_RECORD",
                              {uid}, "RETAINED", {"line": line}))
    return facts, meta

def png_facts(f):
    txt = tool_extract(["tesseract", str(DATASET / f["path"]), "-", "--psm", "6"], f)
    facts = []
    m = re.search(r"(marketing_\d+)\s*[-–]\s*i?\s*([A-Z0-9._%+\-]+@[A-Za-z0-9.\-]+)", txt)
    if m:
        rid, em = m.group(1), m.group(2).lower()
        facts.append(Fact(f["file_id"], f["captured_at"], "marketing_platform", rid, "MARKETING_PROFILE",
                          {em} | refs_of_record(txt), "PRESENT", {"img_text": txt[:600]}))
    return facts

def ingest_all():
    manifest = parse_manifest()
    facts, pdfs = [], {}
    for fid, f in manifest.items():
        try:
            if f["kind"] == "sql": facts += sql_facts(f)
            elif f["kind"] == "json": facts += json_facts(f)
            elif f["kind"] in ("log","txt"): facts += text_facts(f)
            elif f["kind"] == "pdf":
                fr, meta = pdf_facts(f); facts += fr; pdfs[fid] = meta
            elif f["kind"] == "png":
                facts += png_facts(f)
            else:
                print(f"[WARN] unknown kind {f['kind']}", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] parse {fid} failed: {e}", file=sys.stderr)
    return manifest, facts, pdfs


# ============================================================ identity & attribution
IDENT_FIELDS = {"email", "phone", "email_hash"}

class IdentityIndex:
    def __init__(self, identities, audits):
        self.rows = {r["user_id"]: r for r in identities}
        self.uid_values = defaultdict(set)
        self.value_uids = defaultdict(set)
        self.cur_by_email = {}
        for uid, r in self.rows.items():
            self.uid_values[uid].add(uid)
            for k in ("email", "phone", "email_hash"):
                v = r.get(k)
                if not v: continue
                key = norm_ident(v)
                self.uid_values[uid].add(key)
                self.value_uids[key].add(uid)
                if k == "email": self.cur_by_email[v.strip().lower()] = uid
        for a in audits:
            if a["field_name"] not in IDENT_FIELDS: continue
            for v in (a["old_value"], a["new_value"]):
                if not v: continue
                key = norm_ident(v)
                self.uid_values[a["user_id"]].add(key)
                self.value_uids[key].add(a["user_id"])
        self.conflicts = {v: sorted(u) for v, u in self.value_uids.items()
                          if len(u) > 1 and not v.startswith("user_")}

    def resolve(self, email):
        em = email.strip().lower()
        hits = set(self.value_uids.get(em, set()))
        cur = self.cur_by_email.get(em)
        if cur: hits.add(cur)
        if len(hits) == 1: return next(iter(hits)), "exact"
        if len(hits) > 1: return sorted(hits)[0], "ambiguous:" + ",".join(sorted(hits))
        return None, "unresolved"

    def subject_values(self, uid):
        return set(self.uid_values.get(uid, ())) | ({uid} if uid else set())

def norm_ident(v):
    v = str(v).strip()
    return v.lower() if ("@" in v or len(v) > 40) else re.sub(r"\s+", "", v)

class ActivityIndex:
    def __init__(self, rows):
        self.rows = [dict(r, _t=parse_ts(r["event_time"])) for r in rows]
        self.rows.sort(key=lambda r: (r["_t"] or "", r["activity_id"]))
    def worker_window(self, lo, hi):
        return [r for r in self.rows
                if r["source_system"] == "deletion_worker" and lo <= (r["_t"] or "") <= hi]
    def worker_by_rid(self, rid, lo, hi, event_types=None):
        return [r for r in self.worker_window(lo, hi)
                if r["resource_id"] == rid and (not event_types or r["event_type"] in event_types)]

# ---------------------------------------------------------------- attribution
def subject_facts(facts, values, cut, manifest):
    out = []
    for f in facts:
        if not f.rid or f.cat not in RELEVANT_CATS: continue
        f_at = manifest.get(f.file_id, {}).get("captured_at")
        if f.ts and f.ts > cut: continue           # in-document time newer than cutoff
        if f_at and f_at > cut: continue           # file captured after cutoff
        if not f.ts and not f_at: continue
        if f.refs & values:
            out.append(f)
    return out

RELEVANT_CATS = {"USER_PROFILE","SECONDARY_IDENTIFIER","SEARCH_INDEX_ENTRY","SUPPORT_MESSAGE",
                 "SUPPORT_ATTACHMENT","ANALYTICS_PROFILE","ACCOUNT_TOMBSTONE","USER_EXPORT",
                 "MARKETING_PROFILE","EMAIL_DELIVERY_LOG","PRODUCT_TELEMETRY","CACHE_ENTRY",
                 "DATA_FLOW","BACKUP_ARCHIVE","SECURITY_AUDIT_LOG","LEGAL_HOLD_RECORD"}

def bad_state(cat, f, cut):
    p = f.payload
    line = str(p.get("line", "")) + " " + json.dumps(p if isinstance(p, dict) else {})
    st = f.state
    if cat in ("USER_PROFILE", "SECONDARY_IDENTIFIER"):
        if st in ("ABSENT", "NOT_FOUND", "DELETED", "REDACTED") or '"http_status":"404"' in line:
            return False, None
        if st in ("PRESENT", "EXPOSED_PII", "IDENTIFIABLE"):
            return True, "DELETE"
        return None, None
    if cat == "SEARCH_INDEX_ENTRY":
        return (st in ("PRESENT", "HIT")), ("DELETE" if st in ("PRESENT","HIT") else None)
    if cat in ("SUPPORT_ATTACHMENT", "USER_EXPORT", "MARKETING_PROFILE", "CACHE_ENTRY"):
        return (st == "PRESENT"), ("DELETE" if st == "PRESENT" else None)
    if cat == "SUPPORT_MESSAGE":
        # rule_05: only conversations that still carry direct identifiers need redaction;
        # a record holding just the stable internal reference is already redacted.
        has_pii = any("@" in r for r in f.refs) or \
                  any(str(p.get(k) or "").strip('"').lower() not in ("", "none", "null")
                      for k in ("email", "phone", "requester_email", "requester_name",
                                "requester_phone", "email_hash")
                      for p in [f.payload]) or \
                  "@" in str(f.payload.get("message_text", ""))
        if st in ("REDACTED",): return False, None
        if has_pii:
            is_legacy = ("contact_query" in line or "legacy_contact_index" in line
                         or "contact_details" in line)
            return True, ("DELETE" if is_legacy else "REDACT")
        return False, None
    if cat in ("ANALYTICS_PROFILE", "PRODUCT_TELEMETRY"):
        if st == "ANONYMIZED": return False, None
        return (st == "IDENTIFIABLE"), ("ANONYMIZE" if st == "IDENTIFIABLE" else None)
    if cat == "ACCOUNT_TOMBSTONE":
        if st in ("REDACTED",): return False, None
        return (st in ("EXPOSED_PII", "PRESENT")), ("REDACT" if st in ("EXPOSED_PII","PRESENT") else None)
    if cat == "EMAIL_DELIVERY_LOG":
        return (st == "PRESENT" and any("@" in r for r in f.refs)), ("REDACT" if st == "PRESENT" else None)
    if cat == "DATA_FLOW":
        if st == "DISABLED": return False, None
        return (st == "ACTIVE"), ("DISABLE" if st == "ACTIVE" else None)
    if cat == "BACKUP_ARCHIVE":
        if st == "BLOCKED": return False, None
        return (st in ("RESTORE_ALLOWED", "ACTIVE")), ("BLOCK" if st == "RESTORE_ALLOWED" or st == "ACTIVE" else None)
    if cat == "SECURITY_AUDIT_LOG":
        ret = p.get("retention_until")
        if ret and parse_ts(ret) < cut: return True, "DELETE"   # expired retention [rule_12]
        return False, None
    if cat == "LEGAL_HOLD_RECORD":
        return False, None
    return None, None

CAT_TO_VERI = {
    "USER_PROFILE": "VERIFY_RECORD_ABSENT", "SECONDARY_IDENTIFIER": "VERIFY_RECORD_ABSENT",
    "SEARCH_INDEX_ENTRY": "VERIFY_RECORD_ABSENT", "SUPPORT_ATTACHMENT": "VERIFY_RECORD_ABSENT",
    "USER_EXPORT": "VERIFY_RECORD_ABSENT", "MARKETING_PROFILE": "VERIFY_RECORD_ABSENT",
    "CACHE_ENTRY": "VERIFY_RECORD_ABSENT",
    "SUPPORT_MESSAGE": "VERIFY_RECORD_REDACTED", "EMAIL_DELIVERY_LOG": "VERIFY_RECORD_REDACTED",
    "ACCOUNT_TOMBSTONE": "VERIFY_RECORD_REDACTED",
    "ANALYTICS_PROFILE": "VERIFY_RECORD_ANONYMIZED", "PRODUCT_TELEMETRY": "VERIFY_RECORD_ANONYMIZED",
    "DATA_FLOW": "VERIFY_DATA_FLOW_DISABLED", "BACKUP_ARCHIVE": "VERIFY_RESTORE_BLOCKED",
    "SECURITY_AUDIT_LOG": "VERIFY_RECORD_PRESENT", "LEGAL_HOLD_RECORD": "VERIFY_RECORD_PRESENT",
}
CAT_TO_REME = {
    "DELETE": "DELETE_RECORD", "REDACT": "REDACT_RECORD", "ANONYMIZE": "ANONYMIZE_RECORD",
    "DISABLE": "DISABLE_DATA_FLOW", "BLOCK": "BLOCK_RESTORE",
}
FIND_OP = {
    "USER_PROFILE": "REPORT_REMAINING_RECORD", "SECONDARY_IDENTIFIER": "REPORT_REMAINING_RECORD",
    "SEARCH_INDEX_ENTRY": "REPORT_REMAINING_RECORD", "SUPPORT_ATTACHMENT": "REPORT_REMAINING_RECORD",
    "USER_EXPORT": "REPORT_REMAINING_RECORD", "MARKETING_PROFILE": "REPORT_REMAINING_RECORD",
    "CACHE_ENTRY": "REPORT_REMAINING_RECORD",
    "SUPPORT_MESSAGE": "REPORT_EXPOSED_PII", "EMAIL_DELIVERY_LOG": "REPORT_EXPOSED_PII",
    "ACCOUNT_TOMBSTONE": "REPORT_EXPOSED_PII",
    "ANALYTICS_PROFILE": "REPORT_EXPOSED_PII", "PRODUCT_TELEMETRY": "REPORT_EXPOSED_PII",
    "DATA_FLOW": "REPORT_ACTIVE_DATA_FLOW", "BACKUP_ARCHIVE": "REPORT_RESTORE_RISK",
}

def winner_file(facts, cut, manifest):
    """freshest captured_at <= cut, tie: later fact ts, then file_id."""
    best = None
    for f in facts:
        f_at = manifest.get(f.file_id, {}).get("captured_at") or f.ts
        if f_at is None or f_at > cut: continue
        key = (f_at, f.ts or "", f.file_id)
        if best is None or key > best[0]: best = (key, f)
    return best[1] if best else None

def account_support_files(manifest, cut):
    """account-family capture files that can prove an account is absent (no profile row)."""
    out = []
    for fid, f in manifest.items():
        if f["captured_at"] and f["captured_at"] <= cut and "account" in f["path"].lower() and f["kind"] == "sql":
            out.append(f)
    out.sort(key=lambda f: (f["captured_at"], f["file_id"]))
    return out

# ---------------------------------------------------------------- batch anchoring
def batch_anchor_account(req, act, subj_facts, cut):
    """Account rid attribution when no USER_PROFILE evidence fact exists:
    worker DELETE account rows in [requested_at, audit_at]."""
    rows = [r for r in act.worker_window(req["requested_at"], cut)
            if r["event_type"] == "DELETE_RECORD" and r["target_system"] == "account_service"]
    if not rows: return None, "none"
    if len(rows) == 1: return rows[0]["resource_id"], "activity-unique"
    return rows[0]["resource_id"], "activity-multi-first"


# ---------------------------------------------------------------- account attribution
def find_account_rid(req, sf, act, facts, manifest, values, texts):
    """Attribution chain: (1) evidence fact rid, (2) file co-occurrence of subject value +
    account rid, (3) worker DELETE rows in [requested_at, audit_at] nearest reported_at."""
    cut = req["audit_at"]
    acct_facts = [f for f in sf if f.cat == "USER_PROFILE" and f.rid.startswith("account_")]
    if acct_facts:
        return winner_file(acct_facts, cut, manifest).rid, "evidence-fact", None
    # co-occurrence on the same line/record inside eligible files
    big_vals = [v for v in values if len(v) >= 12 and "@" in v] + \
               [v for v in values if len(v) >= 40 and "@" not in v] + \
               [v for v in values if v.startswith("user_")]
    patterns = [re.compile(rf"\b{re.escape(v)}\b", re.I) if v.startswith("user_") else None for v in big_vals]
    cands = {}
    for fid, txt in texts.items():
        f_at = manifest.get(fid, {}).get("captured_at")
        if f_at and f_at > cut: continue
        for line in txt.splitlines():
            low = line.lower()
            matched = False
            for v, p in zip(big_vals, patterns):
                if p:
                    if p.search(line): matched = True; break
                else:
                    if v.lower() in low: matched = True; break
            if not matched: continue
            for m in re.finditer(r"\baccount_[0-9]{1,6}\b", line):
                rid = m.group(0)
                k = (f_at or "", fid)
                if rid not in cands or k > cands[rid]: cands[rid] = k
    if len(cands) == 1:
        return next(iter(cands)), "line-cooccurrence", None
    if len(cands) > 1:
        best = max(cands.items(), key=lambda kv: kv[1])
        return best[0], f"line-cooccurrence({len(cands)})", None
    rows = [r for r in act.worker_window(req["requested_at"], cut)
            if r["event_type"] == "DELETE_RECORD" and r["target_system"] == "account_service"]
    if not rows: return None, "none", None
    if len(rows) == 1:
        return rows[0]["resource_id"], "activity-unique", None
    def dt(r):
        a, b = parse_ts(r["event_time"]), parse_ts(req["reported_at"])
        if a and b:
            return abs(int(a[0:19].replace("-", "").replace("T", "").replace(":", "")) -
                       int(b[0:19].replace("-", "").replace("T", "").replace(":", "")))
        return 0
    pick = sorted(rows, key=lambda r: (dt(r), r["activity_id"]))[0]["resource_id"]
    return pick, f"activity-nearest({len(rows)})", f"account: {len(rows)} delete candidates; picked {pick}"

# ---------------------------------------------------------------- full planner
REME_STATE = {"DELETE": "ABSENT", "REDACT": "REDACTED", "ANONYMIZE": "ANONYMIZED",
              "DISABLE": "DISABLED", "BLOCK": "BLOCKED"}
VERI_STATE = {"USER_PROFILE": "ABSENT", "SECONDARY_IDENTIFIER": "ABSENT",
              "SEARCH_INDEX_ENTRY": "ABSENT", "SUPPORT_ATTACHMENT": "ABSENT",
              "USER_EXPORT": "ABSENT", "MARKETING_PROFILE": "ABSENT", "CACHE_ENTRY": "ABSENT",
              "SUPPORT_MESSAGE": "REDACTED", "EMAIL_DELIVERY_LOG": "REDACTED",
              "ACCOUNT_TOMBSTONE": "REDACTED", "ANALYTICS_PROFILE": "ANONYMIZED",
              "PRODUCT_TELEMETRY": "ANONYMIZED", "DATA_FLOW": "DISABLED",
              "BACKUP_ARCHIVE": "BLOCKED", "SECURITY_AUDIT_LOG": "PRESENT",
              "LEGAL_HOLD_RECORD": "PRESENT"}

def acct_absent_verify(account_rid, sf, cut, manifest):
    """Account verify step: cite a fact proving absence when one exists, else no citation."""
    absence_facts = [f for f in sf if f.rid == account_rid and f.cat == "USER_PROFILE" and
                     (f.state in ("ABSENT", "NOT_FOUND", "DELETED", "REDACTED") or
                      '"http_status":"404"' in json.dumps(f.payload))]
    wf = winner_file(absence_facts, cut, manifest)
    return dict(step_no=0, phase="VERIFICATION", operation="VERIFY_RECORD_ABSENT",
                system_id="account_service", resource_id=account_rid,
                state="ABSENT", evidence_id=wf.file_id if wf else "")

def account_capture_cite(account_rid, cut, manifest):
    """Freshest eligible SQL/DB snapshot capture (proves absence by not listing the profile).
    Falls back to the freshest eligible evidence file of any kind."""
    def num(f):
        try: return int(f["file_id"].split("_")[-1])
        except ValueError: return 0
    cands = [f for fid, f in manifest.items()
             if f["captured_at"] and f["captured_at"] <= cut
             and f["kind"] == "sql" and "databases" in f["path"].lower()]
    if cands:
        f = max(cands, key=lambda f: (f["captured_at"], num(f)))
        return f["file_id"]
    cands = [f for fid, f in manifest.items() if f["captured_at"] and f["captured_at"] <= cut]
    if cands:
        f = max(cands, key=lambda f: (f["captured_at"], num(f)))
        return f["file_id"]
    return ""

def sort_steps(steps):
    order = {"FINDING": FINDING_OPS, "REMEDIATION": REMEDIATION_OPS, "VERIFICATION": VERIFY_OPS}
    def key(s):
        return (PHASE_ORDER[s["phase"]], order[s["phase"]].index(s["operation"]),
                s["system_id"], s["resource_id"])
    steps.sort(key=key)
    for i, s in enumerate(steps, 1):
        s["step_no"] = i
    return steps

def step_json(s):
    return {k: s[k] for k in ("step_no", "phase", "system_id", "resource_id", "operation",
                              "state", "evidence_id")}

_GATE = {"clf": None}

def gate_check(req):
    """Classification gate: NOT_APPLICABLE requests never reach the planner."""
    if _GATE["clf"] is None:
        _GATE["clf"] = RequestClassifier()
    if not req.get("request_text"):
        return None
    return _GATE["clf"].classify(req["case_id"], req["request_text"])

def gate_flush():
    if _GATE["clf"] is not None:
        print("classification log ->", _GATE["clf"].flush())

def report_case(req, ident, act, facts, manifest, secure_log=None):
    gate = gate_check(req)
    if gate == "NOT_APPLICABLE":
        reason = next((r for cid, l, r, m in _GATE["clf"].rows if cid == req["case_id"]), "")
        return dict(status="NOT_APPLICABLE", steps=[],
                    notes=[f"request_text does not authorize deletion ({reason})"],
                    uid=None, account_rid=None, how_acct="gate")
    cut = req["audit_at"]
    uid, how = ident.resolve(req["email"])
    notes = [f"identity={how} uid={uid}"]
    if uid is None:
        notes.append(f"identity unresolved for {req['email']}")
        return dict(status="INCOMPLETE", steps=[], notes=notes)
    values = ident.subject_values(uid)
    sf = subject_facts(facts, values, cut, manifest)
    # loose set for retained-record presence: row timestamp <= cut, file capture may be later
    # (such facts are never cited; they only trigger an uncited VERIFY_RECORD_PRESENT)
    sf_loose = []
    for f in facts:
        if not f.rid or f.cat not in ("SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD"): continue
        f_at = manifest.get(f.file_id, {}).get("captured_at")
        if f.ts and f.ts > cut: continue
        if f_at and f_at > cut and not f.ts: continue
        if f.refs & values:
            sf_loose.append(f)

    groups = defaultdict(list)
    for f in sf:
        groups[(f.system, f.rid, f.cat)].append(f)

    # ---------- account rid (attribution chain)
    account_rid, how_acct, acct_note = find_account_rid(req, sf, act, facts, manifest, values,
                                                        rt_texts.get("texts", {}))
    if acct_note: notes.append(acct_note)
    if account_rid is not None and account_rid not in {k[1] for k in groups}:
        groups[("account_service", account_rid, "USER_PROFILE")] = []   # claimed deleted; no evidence rows remain

    # ---------- per-resource state at audit_at
    findings, remediations = [], []
    remediated_rids = set()
    bad_keys = set()
    compliance_facts_map = {}     # (system, rid, cat) -> winning fact, for COMPLETE citation
    for (system, rid, cat), flist in groups.items():
        if not flist:
            continue                       # activity-only account claim: no evidence -> no finding
        wf = winner_file(flist, cut, manifest)
        bad, action = bad_state(cat, wf, cut)
        if bad:
            bad_keys.add((system, rid, cat))
            op = FIND_OP.get(cat, "REPORT_REMAINING_RECORD")
            if cat == "SUPPORT_MESSAGE" and action == "DELETE":
                op = "REPORT_REMAINING_RECORD"
            find_state = "ACTIVE" if cat in ("DATA_FLOW", "BACKUP_ARCHIVE") else "PRESENT"
            findings.append(dict(step_no=0, phase="FINDING", operation=op, system_id=system,
                                 resource_id=rid, state=find_state, evidence_id=wf.file_id))
            if action:
                r_op = CAT_TO_REME[action]
                remediations.append(dict(step_no=0, phase="REMEDIATION", operation=r_op,
                                         system_id=system, resource_id=rid,
                                         state=REME_STATE[action], evidence_id=""))
                remediated_rids.add((system, rid))
        else:
            compliance_facts_map[(system, rid, cat)] = wf

    # ---------- verifications
    verifications = []
    # 1) account absent: always verified; citation only when the case is COMPLETE
    if account_rid:
        absence_facts = [f for f in sf if f.rid == account_rid and f.cat == "USER_PROFILE" and
                         (f.state in ("ABSENT", "NOT_FOUND", "DELETED", "REDACTED") or
                          '"http_status":"404"' in json.dumps(f.payload))]
        citer = winner_file(absence_facts, cut, manifest)
        cite = citer.file_id if citer else account_capture_cite(account_rid, cut, manifest)
        verifications.append(dict(step_no=0, phase="VERIFICATION", operation="VERIFY_RECORD_ABSENT",
                                  system_id="account_service", resource_id=account_rid,
                                  state="ABSENT", evidence_id=cite))
    # 2) one verify per remediated resource (post-remediation; in INCOMPLETE cases cites are empty)
    REME_TO_VERI = {"DELETE_RECORD": ("VERIFY_RECORD_ABSENT", "ABSENT"),
                    "REDACT_RECORD": ("VERIFY_RECORD_REDACTED", "REDACTED"),
                    "ANONYMIZE_RECORD": ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
                    "DISABLE_DATA_FLOW": ("VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
                    "BLOCK_RESTORE": ("VERIFY_RESTORE_BLOCKED", "BLOCKED")}
    for r in remediations:
        if r["system_id"] == "account_service" and r["resource_id"] == account_rid:
            continue                       # covered by the account-absent verification
        vop, vstate = REME_TO_VERI[r["operation"]]
        verifications.append(dict(step_no=0, phase="VERIFICATION", operation=vop,
                                  system_id=r["system_id"], resource_id=r["resource_id"],
                                  state=vstate, evidence_id=""))
    # 3) retained audit / legal records: verified PRESENT even in INCOMPLETE cases
    for (system, rid, cat) in sorted(compliance_facts_map):
        if cat not in ("SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD"): continue
        verifications.append(dict(step_no=0, phase="VERIFICATION", operation=CAT_TO_VERI[cat],
                                  system_id=system, resource_id=rid, state="PRESENT",
                                  evidence_id=""))
    # 3b) retained records only visible in facts whose file was captured after the cutoff:
    # they still require a retention verification, but always uncited
    loose_retained = set()
    for f in sf_loose:
        loose_retained.add((f.system, f.rid, f.cat))
    for (system, rid, cat) in sorted(loose_retained):
        k = (system, rid, cat)
        if k in compliance_facts_map: continue
        verifications.append(dict(step_no=0, phase="VERIFICATION", operation=CAT_TO_VERI[cat],
                                  system_id=system, resource_id=rid, state="PRESENT",
                                  evidence_id=""))

    status = "INCOMPLETE" if findings else "COMPLETE"
    if status == "COMPLETE":
        # evidence-backed verification only: compliant-state categories found in facts
        for (system, rid, cat), wf in sorted(compliance_facts_map.items()):
            if cat in ("SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD"):
                verifications.append(dict(step_no=0, phase="VERIFICATION",
                                          operation=CAT_TO_VERI[cat], system_id=system,
                                          resource_id=rid, state="PRESENT", evidence_id=wf.file_id))
            elif wf is not None:
                verifications.append(dict(step_no=0, phase="VERIFICATION", operation=CAT_TO_VERI[cat],
                                          system_id=system, resource_id=rid,
                                          state=VERI_STATE[cat], evidence_id=wf.file_id))
        # account verify: keep the cited one
        steps_out = [v for v in verifications if v["evidence_id"]]
    else:
        # INCOMPLETE: findings cite evidence; remediation + verification are future work (empty cite)
        for s in remediations + verifications:
            s["evidence_id"] = ""
        steps_out = findings + remediations + verifications
    # dedupe identical (phase, op, system, rid, state) keeping the first
    seen, dedup = set(), []
    for s in steps_out:
        k = (s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"])
        if k in seen: continue
        seen.add(k); dedup.append(s)
    dedup = sort_steps(dedup)
    for i, s in enumerate(dedup, 1):
        s["step_no"] = i
    return dict(status=status, steps=[step_json(s) for s in dedup], notes=notes,
                uid=uid, account_rid=account_rid, how_acct=how_acct)

def frac_bad(sf):
    return False

# ============================================================ scoring / CLI
def build_runtime():
    requests = load_csv("deletion_requests.csv")
    sample_requests = load_csv("sample_deletion_requests.csv")
    sample_outputs = {r["case_id"]: r for r in load_csv("sample_output.csv")}
    identities = load_csv("user_identities.csv")
    audits = load_csv("user_audit_log.csv")
    activity = load_csv("system_activity.csv")
    manifest, facts, pdfs = ingest_all()
    ident = IdentityIndex(identities, audits)
    act = ActivityIndex(activity)
    texts = {}
    for fid, f in manifest.items():
        try:
            texts[fid] = open(DATASET / f["path"], encoding="utf-8", errors="ignore").read()
        except Exception:
            pass
    return dict(requests=requests, sample_requests=sample_requests, sample_outputs=sample_outputs,
                manifest=manifest, facts=facts, ident=ident, act=act, pdfs=pdfs, texts=texts)

rt_texts = {"texts": {}}

def score_sample(rt, verbose=False, show_mismatches=0):
    outs = rt["sample_outputs"]
    field_match = {"deletion_status": [0,0], "steps": [0,0], "operation": [0,0],
                   "system_id": [0,0], "resource_id": [0,0], "state": [0,0], "evidence_id": [0,0],
                   "order": [0,0], "status_fn":[0,0], "status_fp":[0,0]}
    for req in sorted(rt["sample_requests"], key=lambda r: r["case_id"]):
        cid = req["case_id"]
        exp = json.loads(outs[cid]["steps_json"])
        got = report_case(req, rt["ident"], rt["act"], rt["facts"], rt["manifest"])
        ok_status = got["status"] == outs[cid]["deletion_status"]
        field_match["deletion_status"][0 if ok_status else 1] += 1
        if not ok_status: field_match["status_fn" if got["status"]=="COMPLETE" else "status_fp"][1] += 1
        exp_keys = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in exp]
        got_keys = [(s["phase"], s["operation"], s["system_id"], s["resource_id"], s["state"], s["evidence_id"]) for s in got["steps"]]
        field_match["steps"][0 if exp_keys == got_keys else 1] += 1
        field_match["order"][0 if exp_keys == got_keys else 1] += 1
        # step-level field matches (positionally)
        for i in range(max(len(exp), len(got["steps"]))):
            e = exp[i] if i < len(exp) else None
            g = got["steps"][i] if i < len(got["steps"]) else None
            for fld in ("operation","system_id","resource_id","state","evidence_id"):
                field_match[fld][0 if (e and g and e.get(fld) == g.get(fld)) else 1] += 1
        if verbose or (show_mismatches and (exp_keys != got_keys or not ok_status)):
            print(f"--- {cid} expected {outs[cid]['deletion_status']} got {got['status']} "
                  f"({len(exp)} vs {len(got['steps'])} steps) acct={got.get('account_rid')} {got.get('how_acct','')}")
            if exp_keys != got_keys:
                for i in range(max(len(exp), len(got["steps"]))):
                    e = exp[i] if i < len(exp) else None
                    g = got["steps"][i] if i < len(got["steps"]) else None
                    mark = "OK " if (e and g and all(e[k]==g[k] for k in ("phase","operation","system_id","resource_id","state","evidence_id"))) else "DIF"
                    print(f"  {mark} {exp_keys[i] if i<len(exp_keys) else None}")
                    print(f"      {got_keys[i] if i<len(got_keys) else None}")
    print("\n=== SAMPLE SCORE ===")
    for k, v in field_match.items():
        seen, bad, = v[0], v[1]
        tot = seen + bad
        print(f"  {k:15s} {seen}/{tot} = {seen/max(tot,1):.3f}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="regenerate sample_output and score")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--mismatches", type=int, default=0)
    ap.add_argument("--full", action="store_true", help="all 518 cases -> output.csv")
    a = ap.parse_args()
    rt = build_runtime()
    rt_texts["texts"] = rt["texts"]
    if a.full:
        rows = []
        for req in sorted(rt["requests"], key=lambda r: r["case_id"]):
            res = report_case(req, rt["ident"], rt["act"], rt["facts"], rt["manifest"])
            rows.append({"case_id": req["case_id"], "deletion_status": res["status"],
                         "steps_json": json.dumps(res["steps"], ensure_ascii=False, separators=(",", ":"))})
        out = REPO / "output.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
            w.writeheader(); w.writerows(rows)
        print(f"wrote {out} ({len(rows)} rows)")
        gate_flush()
    else:
        score_sample(rt, verbose=a.verbose, show_mismatches=a.mismatches)
        gate_flush()
