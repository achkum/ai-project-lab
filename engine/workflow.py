"""Persistent, versioned selection and worker leases. No model or shell execution."""
import hashlib
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Invalid identifier")
    return value


def https_url(value):
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("Evidence requires an HTTPS URL")
    return value


COMMON = ("title", "intro", "problem", "outcome", "scope", "possibilities", "market",
          "alternatives", "fit", "effort", "risks", "next_step")
EXTRA = {"thesis": ("question", "prior_work", "contribution", "data", "evaluation"),
         "project": ("acceptance", "demo", "distribution", "maintenance")}


def validate_shortlist(doc):
    identifier(doc["id"])
    if doc["lane"] not in EXTRA or type(doc["version"]) is not int or doc["version"] < 1:
        raise ValueError("Invalid lane/version")
    if not isinstance(doc.get("recommendation_reason"), str) or not doc["recommendation_reason"].strip():
        raise ValueError("Explain the recommendation")
    if not isinstance(doc["candidates"], list) or not 1 <= len(doc["candidates"]) <= 5:
        raise ValueError("Provide 1–5 evidence-backed candidates")
    ids = set()
    for c in doc["candidates"]:
        identifier(c["id"])
        if c["id"] in ids:
            raise ValueError("Duplicate candidate")
        ids.add(c["id"])
        for key in COMMON + EXTRA[doc["lane"]]:
            if not isinstance(c.get(key), str) or not c[key].strip():
                raise ValueError("Missing candidate field: " + key)
        if type(c.get("eligible")) is not bool:
            raise ValueError("Explicit eligibility required")
        if not isinstance(c.get("evidence"), list) or not c["evidence"]:
            raise ValueError("Evidence required")
        for e in c["evidence"]:
            https_url(e["url"])
            if not isinstance(e.get("finding"), str) or not e["finding"].strip():
                raise ValueError("Evidence needs a finding and limitations")
    recommended = next((c for c in doc["candidates"] if c["id"] == doc["recommended"]), None)
    if recommended is None or not recommended["eligible"]:
        raise ValueError("Recommendation must be eligible")


class Workflow:
    def __init__(self, path, owner, private_repo, clock=time.time):
        self.clock, self.owner, self.private_repo = clock, owner, private_repo
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS shortlists(
          id TEXT PRIMARY KEY, lane TEXT NOT NULL, version INTEGER NOT NULL,
          document TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
          published REAL, deadline REAL, issue_url TEXT, selected TEXT,
          origin TEXT, decided REAL, token TEXT, lease_until REAL, result TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_lane ON shortlists(lane)
          WHERE state IN ('draft','awaiting_owner_selection','held','selected','in_progress');
        CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, request TEXT NOT NULL,
          response TEXT NOT NULL, received REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
          shortlist TEXT, kind TEXT, occurred REAL, detail TEXT);
        ''')

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def event(self, sid, kind, detail):
        self.db.execute("INSERT INTO events(shortlist,kind,occurred,detail) VALUES(?,?,?,?)",
                        (sid, kind, self.clock(), canonical(detail)))

    def get(self, sid):
        row = self.db.execute("SELECT * FROM shortlists WHERE id=?", (sid,)).fetchone()
        if row is None:
            raise ValueError("Unknown shortlist")
        return dict(row)

    def rows(self):
        return [dict(x) for x in self.db.execute("SELECT * FROM shortlists ORDER BY created DESC")]

    def submit(self, doc):
        validate_shortlist(doc)
        encoded = canonical(doc)
        with self.transaction():
            old = self.db.execute("SELECT document FROM shortlists WHERE id=?", (doc["id"],)).fetchone()
            if old:
                if old[0] != encoded:
                    raise ValueError("Immutable shortlist changed; cancel it and submit a fresh ID/version")
                return doc["id"]
            self.db.execute("INSERT INTO shortlists(id,lane,version,document,state,created) VALUES(?,?,?,?,?,?)",
                            (doc["id"], doc["lane"], doc["version"], encoded, "draft", self.clock()))
            self.event(doc["id"], "submitted", {})
        return doc["id"]

    def publish(self, sid, issue_url, review_hours=24):
        if not re.fullmatch(r"https://github\.com/" + re.escape(self.private_repo) + r"/issues/[1-9][0-9]*", issue_url):
            raise ValueError("Only the configured private repository decision view is allowed")
        if isinstance(review_hours, bool) or not isinstance(review_hours, (int, float)) or not 0 < review_hours <= 168:
            raise ValueError("Invalid review window")
        with self.transaction():
            row = self.get(sid)
            if row["published"] is not None:
                if row["issue_url"] != issue_url:
                    raise ValueError("Already published elsewhere")
                return row
            now = self.clock()
            self.db.execute("UPDATE shortlists SET state='awaiting_owner_selection',published=?,deadline=?,issue_url=? WHERE id=?",
                            (now, now + review_hours * 3600, issue_url, sid))
            self.event(sid, "published", {"review_hours": review_hours})
            return self.get(sid)

    def _select(self, row, candidate, origin):
        doc = json.loads(row["document"])
        c = next((x for x in doc["candidates"] if x["id"] == candidate), None)
        if not c or not c["eligible"]:
            raise ValueError("Candidate is missing or not eligible")
        self.db.execute("UPDATE shortlists SET state='selected',selected=?,origin=?,decided=? WHERE id=?",
                        (candidate, origin, self.clock(), row["id"]))
        self.event(row["id"], "selected", {"candidate": candidate, "origin": origin, "version": row["version"],
                                          "scope_hash": hashlib.sha256(c["scope"].encode()).hexdigest()})

    def command(self, sid, version, action, candidate, actor, command_id):
        if actor != self.owner:
            raise PermissionError("Only the configured owner can decide")
        if action not in {"select", "hold", "refine", "more", "save", "reject", "resume"}:
            raise ValueError("Unknown action")
        req = canonical([sid, version, action, candidate, actor])
        with self.transaction():
            old = self.db.execute("SELECT * FROM commands WHERE id=?", (command_id,)).fetchone()
            if old:
                if old["request"] != req:
                    raise ValueError("Command ID collision")
                return json.loads(old["response"])
            row = self.get(sid)
            if row["version"] != version or row["published"] is None:
                raise ValueError("Unpublished or stale shortlist")
            if row["state"] == "in_progress":
                # Revoke the lease: an executing worker must recheck before completion/publication.
                self.db.execute("UPDATE shortlists SET state='held',token=NULL,lease_until=NULL WHERE id=?", (sid,))
                result = {"state": "held", "reason": "Work checkpoint required; reselect after reviewing current artifacts"}
            elif row["state"] not in {"awaiting_owner_selection", "held", "selected"}:
                raise ValueError("Decision is already closed")
            elif action == "select":
                self._select(row, candidate, "owner_choice")
                result = {"state": "selected", "candidate": candidate}
            elif action == "resume":
                self.db.execute("UPDATE shortlists SET state='awaiting_owner_selection',deadline=?,selected=NULL,origin=NULL,decided=NULL WHERE id=?",
                                (self.clock() + 86400, sid))
                result = {"state": "awaiting_owner_selection"}
            else:
                state = {"reject": "rejected", "save": "saved"}.get(action, "held")
                self.db.execute("UPDATE shortlists SET state=?,token=NULL,lease_until=NULL WHERE id=?", (state, sid))
                result = {"state": state}
            self.db.execute("INSERT INTO commands VALUES(?,?,?,?)", (command_id, req, canonical(result), self.clock()))
            self.event(sid, "owner_" + action, result)
            return result

    def tick(self, verified_issues):
        """Caller must have fetched current owner comments successfully for these issue URLs."""
        chosen = []
        with self.transaction():
            for row in self.db.execute("SELECT * FROM shortlists WHERE state='awaiting_owner_selection' AND deadline<=?", (self.clock(),)).fetchall():
                if row["issue_url"] not in verified_issues:
                    continue
                doc = json.loads(row["document"])
                self._select(row, doc["recommended"], "authorized_recommended_default")
                chosen.append(row["id"])
        return chosen

    def claim(self, lane, lease_seconds=1800):
        if lane not in EXTRA or not 0 < lease_seconds <= 3600:
            raise ValueError("Invalid claim")
        with self.transaction():
            row = self.db.execute("SELECT * FROM shortlists WHERE lane=? AND (state='selected' OR (state='in_progress' AND lease_until<=?))",
                                  (lane, self.clock())).fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            self.db.execute("UPDATE shortlists SET state='in_progress',token=?,lease_until=? WHERE id=?",
                            (token, self.clock() + lease_seconds, row["id"]))
            doc = json.loads(row["document"])
            candidate = next(x for x in doc["candidates"] if x["id"] == row["selected"])
            self.event(row["id"], "worker_claimed", {})
            return {"shortlist": row["id"], "version": row["version"], "lane": lane, "token": token,
                    "origin": row["origin"], "candidate": candidate, "lease_seconds": lease_seconds}

    def check(self, sid, token):
        row = self.get(sid)
        if row["state"] != "in_progress" or not token or row["token"] != token or row["lease_until"] <= self.clock():
            raise RuntimeError("Worker lease revoked or expired; stop before changing or publishing artifacts")
        return row

    def heartbeat(self, sid, token):
        with self.transaction():
            self.check(sid, token)
            self.db.execute("UPDATE shortlists SET lease_until=? WHERE id=?", (self.clock() + 1800, sid))

    def finish(self, sid, token, result):
        if not isinstance(result, dict) or not all(isinstance(result.get(k), str) and result[k].strip() for k in ("artifact_url", "validation", "limitations")):
            raise ValueError("Completion requires an artifact, validation evidence and limitations")
        https_url(result["artifact_url"])
        with self.transaction():
            self.check(sid, token)
            self.db.execute("UPDATE shortlists SET state='completed',result=?,token=NULL,lease_until=NULL WHERE id=?", (canonical(result), sid))
            self.event(sid, "completed", result)
