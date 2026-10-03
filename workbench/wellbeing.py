"""Private sleep summaries and daily notes, separate from publishable articles."""
import datetime as dt
import json
import math
import os
import secrets
import sqlite3
import time
import uuid
import unicodedata
import urllib.parse
import library


def today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()


def connect():
    library.DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(library.DATA / "wellbeing.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    db.executescript("""
      CREATE TABLE IF NOT EXISTS sleep_days(day TEXT PRIMARY KEY, summary TEXT NOT NULL, received REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS checkins(day TEXT PRIMARY KEY, mood TEXT NOT NULL, updated REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY, kind TEXT NOT NULL, text TEXT NOT NULL, created REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS idea_links(note_id TEXT PRIMARY KEY REFERENCES notes(id), metadata TEXT NOT NULL, revision INTEGER NOT NULL, updated REAL NOT NULL, updated_by TEXT NOT NULL);
    """)
    return db


def upload_key():
    path = library.DATA / "health-upload.key"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(secrets.token_urlsafe(40))
    except FileExistsError:
        pass
    return path.read_text().strip()


def upload_authorized(header):
    token = header.removeprefix("Bearer ")
    return bool(token) and secrets.compare_digest(token, upload_key())


def import_sleep(body):
    metrics = body.get("data", {}).get("metrics", [])
    if not isinstance(metrics, list):
        raise ValueError("睡眠数据格式错误")
    rows = []
    for metric in metrics:
        if not isinstance(metric, dict) or metric.get("name") != "sleep_analysis":
            continue
        if metric.get("units") != "hr" or not isinstance(metric.get("data"), list):
            raise ValueError("请选择按天汇总的睡眠数据，单位为小时")
        for raw in metric["data"]:
            if not isinstance(raw, dict):
                raise ValueError("睡眠记录格式错误")
            day = str(raw.get("date") or raw.get("end") or raw.get("start") or "")[:10]
            dt.date.fromisoformat(day)
            record = {"day": day}
            for key in ("totalSleep", "core", "deep", "rem"):
                value = raw.get(key)
                if value is None and key != "totalSleep":
                    continue
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 24:
                    raise ValueError("睡眠时长需要是 0 到 24 小时的有限数值")
                record[key] = value
            # Daily aggregation boundaries are not actual bedtime/wake time.
            for key in ("sleepStart", "sleepEnd", "sources"):
                if isinstance(raw.get(key), str):
                    record[key] = raw[key][:300]
            rows.append((day, json.dumps(record, ensure_ascii=False), time.time()))
    if not rows or len(rows) > 370:
        raise ValueError("需要 1 到 370 条按天汇总的睡眠记录")
    with connect() as db:
        db.executemany("INSERT INTO sleep_days VALUES (?,?,?) ON CONFLICT(day) DO UPDATE SET summary=excluded.summary,received=excluded.received", rows)
    return {"imported": len({r[0] for r in rows})}


def snapshot():
    with connect() as db:
        sleep = [{**json.loads(r["summary"]), "received": r["received"]} for r in db.execute("SELECT * FROM sleep_days ORDER BY day DESC LIMIT 30")]
        checkins = [dict(r) for r in db.execute("SELECT * FROM checkins ORDER BY day DESC LIMIT 30")]
        notes = [dict(r) for r in db.execute("SELECT * FROM notes ORDER BY created DESC LIMIT 60")]
    return {"today": today(), "sleep": sleep, "checkins": checkins, "notes": notes}


def check_in(body):
    mood = body.get("mood")
    if mood not in ("good", "okay", "tired"):
        raise ValueError("请选择今天的感受")
    with connect() as db:
        db.execute("INSERT INTO checkins VALUES (?,?,?) ON CONFLICT(day) DO UPDATE SET mood=excluded.mood,updated=excluded.updated", (today(), mood, time.time()))
    return {"day": today(), "mood": mood}


def save_note(body):
    kind, text, note_id = body.get("kind"), body.get("text"), body.get("id")
    if kind not in ("idea", "reflection") or not isinstance(text, str) or not text.strip() or len(text) > 50000:
        raise ValueError("请写下 1 到 50000 字的想法")
    if not isinstance(note_id, str):
        raise ValueError("记录编号格式错误")
    uuid.UUID(note_id)
    with connect() as db:
        old = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if old:
            if old["text"] != text.strip() or old["kind"] != kind:
                raise library.Conflict("这条记录已保存了不同内容，请先核对")
            return dict(old)
        note = {"id": note_id, "kind": kind, "text": text.strip(), "created": time.time()}
        db.execute("INSERT INTO notes VALUES (:id,:kind,:text,:created)", note)
    return note


def ideas():
    with connect() as db:
        rows = db.execute("SELECT n.*,i.metadata,i.revision,i.updated,i.updated_by FROM notes n LEFT JOIN idea_links i ON i.note_id=n.id WHERE n.kind='idea' ORDER BY n.created DESC").fetchall()
    return [{"id": r["id"], "text": r["text"], "created": r["created"],
             "revision": r["revision"] or 0, "updated": r["updated"], "updated_by": r["updated_by"],
             "keywords": [], "context": "", "next_step": "", "source_label": "", "source_url": "",
             **json.loads(r["metadata"] or "{}")} for r in rows]


def save_idea_links(body):
    note_id, revision = body.get("id"), body.get("revision")
    if not isinstance(note_id, str) or isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise ValueError("请提供灵感编号和当前关联版本")
    keywords = body.get("keywords", [])
    if not isinstance(keywords, list) or len(keywords) > 32:
        raise ValueError("关键词需为列表，最多 32 个")
    labels, seen = [], set()
    for word in keywords:
        if not isinstance(word, str) or not word.strip() or len(word.strip()) > 40:
            raise ValueError("每个关键词需要 1 到 40 个字")
        label = unicodedata.normalize("NFC", word.strip())
        if label.lower() not in seen:
            labels.append(label); seen.add(label.lower())
    metadata = {"keywords": labels}
    for key, limit in (("context", 10000), ("next_step", 10000), ("source_label", 200), ("source_url", 2000)):
        value = body.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("关联说明格式错误或过长")
        metadata[key] = value.strip()
    if metadata["source_url"]:
        parsed = urllib.parse.urlsplit(metadata["source_url"])
        web = parsed.scheme in ("http", "https") and bool(parsed.hostname)
        chat = parsed.scheme == "codex" and parsed.netloc == "threads" and len(parsed.path) > 1
        if not (web or chat) or parsed.username or parsed.password:
            raise ValueError("来源链接需要是网页地址或 Codex 会话链接")
    source = body.get("source", "zelong/网页整理")
    if not isinstance(source, str) or len(source) > 80:
        raise ValueError("整理者格式错误")
    encoded = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        note = db.execute("SELECT kind FROM notes WHERE id=?", (note_id,)).fetchone()
        if not note or note["kind"] != "idea":
            raise ValueError("这条灵感不存在")
        old = db.execute("SELECT * FROM idea_links WHERE note_id=?", (note_id,)).fetchone()
        if old and old["metadata"] == encoded:
            return {"id": note_id, "revision": old["revision"], **metadata}
        if (old["revision"] if old else 0) != revision:
            raise library.Conflict("这条灵感的关联已有更新，请重新读取，当前输入不要丢弃")
        db.execute("INSERT INTO idea_links VALUES (?,?,?,?,?) ON CONFLICT(note_id) DO UPDATE SET metadata=excluded.metadata,revision=excluded.revision,updated=excluded.updated,updated_by=excluded.updated_by", (note_id, encoded, revision + 1, time.time(), source))
    return {"id": note_id, "revision": revision + 1, **metadata}
