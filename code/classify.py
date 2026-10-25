"""Deterministic multilingual request_text classifier for the deletion gate.

Labels
  DELETE          the text authorizes erasure of the person's data
  NOT_APPLICABLE  access/export, correction, password/login help, marketing
                  opt-out, keep-the-account / withdrawal, or a negated deletion

Method: deterministic keyword/negation rules first.  If an LLM is configured
via environment variables it is consulted ONLY for ambiguous cases (no rule
fired), with a JSON on-disk cache.  Without an API key the pipeline runs on
rules alone.
"""
import csv, json, os, re, sys, urllib.request
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent / "evaluation" if False else \
    Path(__file__).resolve().parent / "evaluation"
LOG_PATH = EVAL_DIR / "classification_log.csv"
LLM_CACHE_PATH = EVAL_DIR / "llm_cache.json"

# --- non-deletion signal families (checked BEFORE deletion keywords) ---------
# negation / keep: these dominate, e.g. "This is an information request, not a
# request to erase it." still contains the keyword erase.
NEGATION = [
    r"not (?:a |the )?(?:request|asking|asking for|hereby|soliciting)? ?(?:to |for )?(?:erase|delete|deletion|remove|removal)",
    r"not (?:a deletion request|a deletion|deleting)",
    r"do not close", r"don'?t close", r"do not delete", r"don'?t delete",
    r"don'?t (?:delete|remove) anything", r"without removing", r"leave (?:my |the )?account",
    r"keep (?:my |the )?account", r"account (?:stay|remain)s? active",
    r"leave my profile", r"keep the account as it is", r"keep the account active",
    r"still need the account", r"still use it", r"i still use",
    r"continue using (?:the |this )?service", r"still want",
]
WITHDRAW = [
    r"withdraw", r"cancel my (?:previous )?request", r"revoke my request",
    r"ignore my (?:previous|earlier) request", r"retiro mi solicitud",
    r"retirer ma demande",
]
LOGIN = [
    r"password", r"reset (?:the |my )?login", r"can'?t (?:log ?in|access)",
    r"cannot (?:log ?in|access)", r"locked out", r"two-?factor", r"login help",
    r"sign ?in (?:help|problem)", r"contraseña", r"mot de passe", r"パスワード",
    r"비밀번호", r"senha",
]
ACCESS = [
    r"download", r"portable format", r"copy of (?:the |my |last)", r"send me a copy",
    r"a copy of the information", r"what (?:personal )?information you hold",
    r"information request", r"subject access", r"access (?:to )?my (?:data|information|personal)",
    r"access request", r"export (?:my |a copy)", r"obtener una copia", r"obtenir une copie",
    r"사본", r"コピー", r"cópia dos meus",
]
CORRECTION = [
    r"correct (?:it|my|the)", r"misspelled", r"out of date", r"replace it",
    r"change the email", r"fix (?:my |the )?", r"rectif", r"update (?:my |the )?(?:email|phone|name|address)",
    r"actualizar", r"mettre à jour", r"修正", r"수정", r"atualizar", r"corriger",
]
MARKETING = [
    r"marketing lists?", r"promotional emails?", r"newsletters?", r"unsubscribe",
    r"marketing communications?", r"correos promocionales", r"e-?mails promotionnels",
    r"プロモーション", r"프로모션", r"e-?mails? promocionais",
]
THIRD_PARTY = [
    r"on behalf of", r"my (?:son|daughter|wife|husband|spouse|employee|father|mother|brother|sister)",
    r"em nome de", r"de la part de",
]

# --- deletion-intent keywords (any of these, without a blocking signal above) -
DELETION = [
    # en
    r"\bdelet", r"\beras", r"\bremoval\b", r"\bremoval|removed\b",
    r"remove my account", r"remove the account", r"\bpurge\b", r"\bwipe\b",
    r"be forgotten", r"cease processing", r"close (?:this|my|the) account",
    r"no longer use (?:this|my|the) account", r"de-?identifi",
    # es / pt / fr / it / de
    r"eliminaci", r"eliminar", r"suprimir", r"supresión", r"borrado", r"borrar",
    r"exclus", r"excluir", r"apagar", r"remover minha conta", r"apaga[rdo]",
    r"suppression", r"supprimer", r"effacer", r"annullamento", r"eliminazione",
    r"cancellazione", r"löschung", r"löschen", r"entfernen",
    # cjk / ko
    r"削除", r" 삭제", r"删除",
]

COMPILED = {k: [re.compile(p, re.I) for p in v]
            for k, v in dict(NEGATION=NEGATION, WITHDRAW=WITHDRAW, LOGIN=LOGIN,
                             ACCESS=ACCESS, CORRECTION=CORRECTION, MARKETING=MARKETING,
                             THIRD_PARTY=THIRD_PARTY, DELETION=DELETION).items()}


def _first_match(text, fam):
    for rx in COMPILED[fam]:
        m = rx.search(text)
        if m:
            return m.group(0)[:60]
    return None


def rule_classify(text):
    """returns (label, reason, method). label in DELETION / NOT_APPLICABLE / AMBIGUOUS"""
    # 1) explicit negation / withdrawal dominates even when deletion words appear
    for fam in ("NEGATION", "WITHDRAW"):
        m = _first_match(text, fam)
        if m:
            return "NOT_APPLICABLE", f"{fam.lower()} signal: '{m}'", "rules"
    # 2) non-deletion request families, only when no deletion intent exists
    gate = _first_match(text, "DELETION")
    if gate is None:
        for fam in ("LOGIN", "ACCESS", "CORRECTION", "MARKETING", "THIRD_PARTY"):
            m = _first_match(text, fam)
            if m:
                return "NOT_APPLICABLE", f"{fam.lower()} signal: '{m}'", "rules"
        return "AMBIGUOUS", "no classification signal", "rules"
    return "DELETION", f"deletion intent: '{gate}'", "rules"


# ------------------------------------------------------------- optional LLM ---
CFG = {
    "provider": os.environ.get("LLM_PROVIDER", ""),
    "model": os.environ.get("LLM_MODEL", ""),
    "api_key": os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
    "base_url": os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
}
_llm_cache = None
if LLM_CACHE_PATH.exists():
    try: _llm_cache = json.loads(LLM_CACHE_PATH.read_text())
    except Exception: _llm_cache = {}
_llm_cache = _llm_cache or {}

LLM_PROMPT = (
    "You are gating GDPR requests. Reply with strict JSON {\"label\": \"DELETE\""
    " | \"NOT_APPLICABLE\"} and nothing else. DELETE only when the sender asks"
    " for erasure/deletion of their own personal data or account. NOT_APPLICABLE"
    " for access/export copies, corrections/updates, login or password help,"
    " marketing opt-out, keep-the-account phrasing, request withdrawal, or"
    " unauthorised third-party requests.\nText: {text}"
)


def _llm_call(text):
    if not (CFG["api_key"] and CFG["model"]):
        return None
    key = text
    if key in _llm_cache:
        return _llm_cache[key].get("label")
    body = json.dumps({"model": CFG["model"], "temperature": 0,
                       "messages": [{"role": "user", "content": LLM_PROMPT.format(text=text)}]}).encode()
    req = urllib.request.Request(
        f"{CFG['base_url']}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CFG['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode())
        content = out["choices"][0]["message"]["content"]
        label = json.loads(re.search(r"\{.*\}", content, re.S).group(0))["label"]
        label = label if label in ("DELETE", "NOT_APPLICABLE") else None
    except Exception as e:
        label = None
    _llm_cache[key] = {"label": label}
    LLM_CACHE_PATH.write_text(json.dumps(_llm_cache, ensure_ascii=False, indent=1))
    return label


class RequestClassifier:
    """Deterministic-first gate with optional LLM fallback for ambiguous texts."""

    def __init__(self, log_path=LOG_PATH):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.rows = []
        self.labels = {}

    def classify(self, case_id, text):
        label, reason, method = rule_classify(text)
        if label == "AMBIGUOUS":
            llm_label = _llm_call(text)
            if llm_label:
                label, method = llm_label, "llm"
                reason = "llm decision (ambiguous text, no keyword signal)"
            else:
                label, method = "DELETION", "default"
                reason = "ambiguous: no signal; deletion assumed (dataset default)"
        self.labels[case_id] = label
        self.rows.append((case_id, label, reason, method))
        return label

    def flush(self):
        with open(self.log_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["case_id", "label", "reason", "method"])
            w.writerows(self.rows)
        return str(self.log_path)


if __name__ == "__main__":
    import sys
    rc = RequestClassifier()
    rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
    for r in rows:
        rc.classify(r["case_id"], r["request_text"])
    print("wrote", rc.flush())
