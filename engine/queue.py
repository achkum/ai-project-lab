"""Private local runtime queue. No network endpoint or arbitrary code execution."""
import json
import sqlite3
import time
import uuid
from pathlib import Path

class Queue:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, dedupe_key TEXT UNIQUE NOT NULL,
          lane TEXT NOT NULL CHECK(lane IN ('thesis','project')),
          task TEXT NOT NULL, payload TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'queued',
          worker TEXT, token TEXT, lease_until REAL,
          attempts INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL,
          created_at REAL NOT NULL, updated_at REAL NOT NULL,
          result TEXT
        );
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT OR IGNORE INTO metadata VALUES('schema_version','1');
        """)
        if self.db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] != "1":
            raise RuntimeError("Unsupported queue schema")

    def close(self):
        self.db.close()

    def enqueue(self, dedupe_key, lane, task, payload=None, max_attempts=3):
        if lane not in ("thesis", "project") or not dedupe_key or not task:
            raise ValueError("A valid lane, task and deduplication key are required")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        encoded = json.dumps(payload or {}, sort_keys=True)
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute("SELECT * FROM jobs WHERE dedupe_key=?", (dedupe_key,)).fetchone()
            if existing:
                if (existing["lane"], existing["task"], existing["payload"]) != (lane, task, encoded):
                    raise ValueError("Deduplication key reused with a different request")
                job_id = existing["id"]
            else:
                job_id = uuid.uuid4().hex
                self.db.execute("""INSERT INTO jobs
                  (id,dedupe_key,lane,task,payload,max_attempts,created_at,updated_at)
                  VALUES(?,?,?,?,?,?,?,?)""",
                  (job_id,dedupe_key,lane,task,encoded,max_attempts,now,now))
            self.db.execute("COMMIT")
            return job_id
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def claim(self, worker, lane, lease_seconds=120):
        if not worker or lane not in ("thesis", "project") or lease_seconds <= 0:
            raise ValueError("Invalid worker, lane or lease")
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("""UPDATE jobs SET state=CASE WHEN attempts>=max_attempts
              THEN 'failed' ELSE 'queued' END, worker=NULL, token=NULL, lease_until=NULL,
              updated_at=? WHERE state='running' AND lease_until<=?""", (now,now))
            row = self.db.execute("""SELECT * FROM jobs WHERE lane=? AND state='queued'
              AND attempts<max_attempts ORDER BY created_at,id LIMIT 1""",(lane,)).fetchone()
            if row is None:
                self.db.execute("COMMIT")
                return None
            token = uuid.uuid4().hex
            self.db.execute("""UPDATE jobs SET state='running',worker=?,token=?,lease_until=?,
              attempts=attempts+1,updated_at=? WHERE id=?""",
              (worker,token,now+lease_seconds,now,row["id"]))
            result = dict(self.db.execute("SELECT * FROM jobs WHERE id=?",(row["id"],)).fetchone())
            self.db.execute("COMMIT")
            result["payload"] = json.loads(result["payload"])
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def heartbeat(self, job_id, token, lease_seconds=120):
        if lease_seconds <= 0:
            raise ValueError("Lease must be positive")
        now = self.clock()
        changed = self.db.execute("""UPDATE jobs SET lease_until=?,updated_at=?
          WHERE id=? AND token=? AND state='running' AND lease_until>?""",
          (now+lease_seconds,now,job_id,token,now)).rowcount
        if not changed:
            raise RuntimeError("Lease lost; stop this attempt")

    def finish(self, job_id, token, result):
        now = self.clock()
        changed = self.db.execute("""UPDATE jobs SET state='completed',result=?,token=NULL,
          lease_until=NULL,updated_at=? WHERE id=? AND token=? AND state='running'
          AND lease_until>?""",(json.dumps(result),now,job_id,token,now)).rowcount
        if not changed:
            raise RuntimeError("Lease lost; completion rejected")

    def summary(self):
        # Public-safe aggregate only. Never return payloads, titles or worker names here.
        return {row["state"]:row["n"] for row in self.db.execute(
            "SELECT state,COUNT(*) AS n FROM jobs GROUP BY state")}

