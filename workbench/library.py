"""Single-owner article storage; SQLite transactions protect concurrent edits."""
import hashlib
import json
import os
import secrets
import sqlite3
import time
import tempfile
import uuid
from pathlib import Path

DATA = Path(os.environ.get("WORKBENCH_DATA_DIR", str(Path(__file__).parent / ".data")))


class Conflict(Exception):
    pass


def connect():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(DATA / "articles.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY, document TEXT NOT NULL, revision INTEGER NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0, updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS versions (
            article_id TEXT, revision INTEGER, document TEXT, archived INTEGER,
            updated REAL, source TEXT, PRIMARY KEY(article_id, revision));
        CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, expires REAL);
        CREATE TABLE IF NOT EXISTS login_codes (digest TEXT PRIMARY KEY, expires REAL);
        CREATE TABLE IF NOT EXISTS draft_receipts (fingerprint TEXT PRIMARY KEY, receipt TEXT);
    """)
    return db


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def owner_key():
    connect().close()
    path = DATA / "owner.key"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(secrets.token_urlsafe(40))
    except FileExistsError:
        pass
    return path.read_text().strip()


def login_code():
    code = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("DELETE FROM login_codes WHERE expires < ?", (time.time(),))
        db.execute("INSERT INTO login_codes VALUES (?,?)", (digest(code), time.time() + 600))
    return code


def set_password(password):
    if not isinstance(password, str) or not password:
        raise ValueError("密码不能为空")
    connect().close()
    salt = secrets.token_bytes(16)
    value = {"salt": salt.hex(), "hash": hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex()}
    with tempfile.NamedTemporaryFile(mode="w", dir=DATA, delete=False) as out:
        json.dump(value, out)
        path = out.name
    os.replace(path, DATA / "password.json")


def password_matches(password):
    try:
        value = json.loads((DATA / "password.json").read_text())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(value["salt"]), 600000).hex()
        return secrets.compare_digest(actual, value["hash"])
    except (OSError, ValueError, KeyError):
        return False


def login(code):
    if not isinstance(code, str):
        return None
    valid_password = password_matches(code)
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        result = db.execute("DELETE FROM login_codes WHERE digest=? AND expires>?", (digest(code), time.time()))
        if result.rowcount != 1 and not valid_password:
            return None
        token = secrets.token_urlsafe(40)
        db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        db.execute("INSERT INTO sessions VALUES (?,?)", (digest(token), time.time() + 30 * 86400))
        return token


def authorized(bearer, cookie):
    if bearer and secrets.compare_digest(bearer, owner_key()):
        return True
    with connect() as db:
        return bool(db.execute("SELECT 1 FROM sessions WHERE digest=? AND expires>?", (digest(cookie), time.time())).fetchone())


def unpack(row):
    return {"id": row["id"], "document": json.loads(row["document"]), "revision": row["revision"], "archived": bool(row["archived"]), "updated": row["updated"]}


def list_articles():
    with connect() as db:
        rows = db.execute("SELECT * FROM articles ORDER BY updated DESC").fetchall()
    results = []
    for row in rows:
        item = unpack(row)
        doc = item.pop("document")
        results.append({**item, "title": doc.get("title", "未命名文章"), "digest": doc.get("digest", ""), "wechat": doc.get("wechat")})
    return results


def get_article(article_id, revision=None):
    with connect() as db:
        if revision is None:
            row = db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        else:
            row = db.execute("SELECT article_id AS id,document,revision,archived,updated FROM versions WHERE article_id=? AND revision=?", (article_id, revision)).fetchone()
    return unpack(row) if row else None


def versions(article_id):
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT revision,updated,source FROM versions WHERE article_id=? ORDER BY revision DESC", (article_id,))]


def save_article(body):
    article_id = body.get("id") or str(uuid.uuid4())
    if not isinstance(article_id, str) or len(article_id) > 100:
        raise ValueError("文章编号格式错误")
    document = body.get("document")
    if not isinstance(document, dict):
        raise ValueError("文章格式错误")
    for name in ("title", "markdown", "byline", "author", "digest", "theme", "cover"):
        if name in document and not isinstance(document[name], str):
            raise ValueError("文章字段格式错误")
    if not document.get("title", "").strip():
        raise ValueError("请先填写文章标题")
    if not isinstance(document.get("images", {}), dict):
        raise ValueError("配图格式错误")
    revision = body.get("revision", 0)
    if not isinstance(revision, int):
        raise ValueError("文章版本格式错误")
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True)
    if len(encoded.encode()) > 15_000_000:
        raise ValueError("文章图片过大，请压缩后保存")
    archived = int(bool(body.get("archived", False)))
    source = str(body.get("source", "网页编辑"))[:80]
    now = time.time()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        if old and old["document"] == encoded and old["archived"] == archived:
            return unpack(old)
        if (old["revision"] if old else 0) != revision:
            raise Conflict("文章已在另一处更新，请保留当前修改另存一份。")
        revision += 1
        db.execute("INSERT INTO articles VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET document=excluded.document,revision=excluded.revision,archived=excluded.archived,updated=excluded.updated", (article_id, encoded, revision, archived, now))
        # ponytail: full snapshots fit a personal library; deduplicate images if storage grows.
        db.execute("INSERT INTO versions VALUES (?,?,?,?,?,?)", (article_id, revision, encoded, archived, now, source))
    return {"id": article_id, "document": document, "revision": revision, "archived": bool(archived), "updated": now}


def receipt_get(fingerprint):
    with connect() as db:
        row = db.execute("SELECT receipt FROM draft_receipts WHERE fingerprint=?", (fingerprint,)).fetchone()
    return json.loads(row[0]) if row else None


def receipt_put(fingerprint, value):
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO draft_receipts VALUES (?,?)", (fingerprint, json.dumps(value)))


def receipt_delete(fingerprint):
    with connect() as db:
        db.execute("DELETE FROM draft_receipts WHERE fingerprint=?", (fingerprint,))
