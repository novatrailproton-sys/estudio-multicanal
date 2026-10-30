from __future__ import annotations

import contextlib
import json
from pathlib import Path
import sqlite3
import time
import uuid


def uid():
    return uuid.uuid4().hex


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("assets", "work", "cache", "exports"):
            (self.root / name).mkdir(exist_ok=True)
        self.path = self.root / "studio.sqlite3"
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, data TEXT NOT NULL,
              revision INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              kind TEXT NOT NULL, status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
              message TEXT NOT NULL DEFAULT '', next_run REAL NOT NULL DEFAULT 0,
              attempts INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL,
              data TEXT NOT NULL DEFAULT '{}');
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_production ON jobs(project_id)
              WHERE status IN ('queued','running','waiting') AND kind != 'publish';
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, job_id TEXT NOT NULL,
              at REAL NOT NULL, message TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              path TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS quotas(provider TEXT PRIMARY KEY, next_allowed REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
              revision INTEGER NOT NULL, platform TEXT NOT NULL, account TEXT NOT NULL,
              status TEXT NOT NULL, data TEXT NOT NULL,
              UNIQUE(project_id, revision, platform, account));
            """)

    @contextlib.contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_channels(self):
        with self.connect() as db:
            return [{"id": r["id"], **json.loads(r["data"])} for r in db.execute("SELECT * FROM channels")]

    def save_channel(self, value, identifier=None):
        identifier = identifier or uid()
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO channels VALUES (?,?)", (identifier, dumps(value)))
        return identifier

    def channel(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT data FROM channels WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Canal no encontrado.")
        return {"id": identifier, **json.loads(row[0])}

    def create_project(self, data):
        self.channel(data["channel_id"])
        identifier = uid()
        data = {**data, "scenes": [], "review": {}, "state": "draft", "audio_asset": None,
                "music_asset": None, "timing": "estimated", "output_asset": None}
        with self.connect() as db:
            db.execute("INSERT INTO projects VALUES (?,?,1,?,?)", (identifier, dumps(data), time.time(), time.time()))
        return self.project(identifier)

    def project(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Proyecto no encontrado.")
        return {**json.loads(row["data"]), "id": row["id"], "revision": row["revision"],
                "created": row["created"], "updated": row["updated"]}

    def list_projects(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM projects ORDER BY updated DESC")]
        return [self.project(i) for i in ids]

    def change(self, identifier, changes, expected=None, content=True):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data,revision FROM projects WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise ValueError("Proyecto no encontrado.")
            if expected is not None and expected != row["revision"]:
                raise ValueError("El proyecto cambió. Actualiza la pantalla antes de guardar.")
            value = json.loads(row["data"])
            value.update(changes)
            if content:
                value.update(review={}, output_asset=None, cover_asset=None, state="draft")
            db.execute("UPDATE projects SET data=?,revision=?,updated=? WHERE id=?",
                       (dumps(value), row["revision"] + int(content), time.time(), identifier))
        return self.project(identifier)

    def enqueue(self, project_id, kind, data=None, when=0):
        self.project(project_id)
        identifier, now = uid(), time.time()
        with self.connect() as db:
            try:
                db.execute("INSERT INTO jobs(id,project_id,kind,status,next_run,created,updated,data) VALUES (?,?,?,'queued',?,?,?,?)",
                           (identifier, project_id, kind, when, now, now, dumps(data or {})))
            except sqlite3.IntegrityError:
                raise ValueError("Este proyecto ya tiene un trabajo pendiente. Cancélalo o espera a que termine.") from None
        return self.job(identifier)

    def jobs(self, project_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM jobs " + ("WHERE project_id=? " if project_id else "") + "ORDER BY created DESC LIMIT 200",
                              (project_id,) if project_id else ()).fetchall()
        return [{**dict(r), "data": json.loads(r["data"])} for r in rows]

    def job(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Trabajo no encontrado.")
        return {**dict(row), "data": json.loads(row["data"])}

    def set_job(self, identifier, **changes):
        if not changes.keys() <= {"status", "progress", "message", "next_run", "data", "attempts"}:
            raise ValueError("Cambio de trabajo no permitido.")
        if "data" in changes:
            changes["data"] = dumps(changes["data"])
        changes["updated"] = time.time()
        with self.connect() as db:
            db.execute("UPDATE jobs SET " + ",".join(k+"=?" for k in changes) + " WHERE id=?", (*changes.values(), identifier))

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE status IN ('queued','waiting') AND next_run<=? ORDER BY created LIMIT 1", (time.time(),)).fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',attempts=attempts+1,updated=? WHERE id=?", (time.time(), row[0]))
        return self.job(row[0])

    def recover(self):
        with self.connect() as db:
            # Never repeat an external publication whose outcome may have been lost.
            db.execute("UPDATE publications SET status='unknown' WHERE status='uploading'")
            db.execute("UPDATE jobs SET status='review',message='Revisar resultado externo antes de reintentar' WHERE kind='publish' AND status='running'")
            db.execute("UPDATE jobs SET status='queued',message='Recuperado tras reinicio' WHERE status='running'")

    def log(self, job_id, message):
        with self.connect() as db:
            db.execute("INSERT INTO events(job_id,at,message) VALUES (?,?,?)", (job_id, time.time(), message[:1000]))
            db.execute("UPDATE jobs SET message=?,updated=? WHERE id=?", (message[:500], time.time(), job_id))

    def events(self, job_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT at,message FROM events WHERE job_id=? ORDER BY id DESC LIMIT 100", (job_id,))]

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT data FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def save_setting(self, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, dumps(value)))

    def add_asset(self, project_id, path, data):
        path = Path(path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Recurso fuera del directorio de trabajo.")
        identifier = uid()
        with self.connect() as db:
            db.execute("INSERT INTO assets VALUES (?,?,?,?,?)", (identifier, project_id, str(path.relative_to(self.root)), dumps(data), time.time()))
        return self.asset(identifier)

    def asset(self, identifier, project_id=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM assets WHERE id=?", (identifier,)).fetchone()
        if not row or (project_id is not None and row["project_id"] != project_id):
            raise ValueError("Recurso no encontrado en este proyecto.")
        return {"id": row["id"], "project_id": row["project_id"], "path": row["path"], **json.loads(row["data"])}

    def asset_path(self, identifier, project_id=None):
        path = (self.root / self.asset(identifier, project_id)["path"]).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError("Archivo del recurso no disponible.")
        return path

    def assets(self, project_id):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM assets WHERE project_id=? ORDER BY created", (project_id,))]
        return [self.asset(i) for i in ids]
