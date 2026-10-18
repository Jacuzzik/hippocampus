"""SQLite index for one vault.

The index is a cache of the notes. It is safe to delete at any time: a missing,
corrupt or out-of-date file is removed and rebuilt from the vault.
"""

import hashlib
import logging
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from core.vault.parser import ParsedNote, normalize_target
from core.vault.scanner import NoteFile

logger = logging.getLogger("hippocampus.core.vault")

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE notes (
    id           INTEGER PRIMARY KEY,
    path         TEXT NOT NULL UNIQUE,
    path_key     TEXT NOT NULL,
    name_key     TEXT NOT NULL,
    title        TEXT NOT NULL,
    mtime_ns     INTEGER NOT NULL,
    size         INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    indexed_at   INTEGER NOT NULL
);

CREATE TABLE links (
    source_id  INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_raw TEXT NOT NULL,
    target_key TEXT NOT NULL,
    alias      TEXT,
    heading    TEXT,
    is_embed   INTEGER NOT NULL DEFAULT 0,
    line       INTEGER NOT NULL
);

CREATE TABLE tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    tag_key TEXT NOT NULL,
    source  TEXT NOT NULL CHECK (source IN ('inline', 'frontmatter')),
    UNIQUE (note_id, tag_key, source)
);

CREATE INDEX notes_name_key   ON notes(name_key);
CREATE INDEX notes_path_key   ON notes(path_key);
CREATE INDEX links_source     ON links(source_id);
CREATE INDEX links_target_key ON links(target_key);
CREATE INDEX tags_tag_key     ON tags(tag_key);

CREATE VIEW resolved_links AS
SELECT l.rowid AS link_id, l.*,
       (SELECT n.id FROM notes n
         WHERE n.path_key = l.target_key OR n.name_key = l.target_key
         ORDER BY (n.path_key = l.target_key) DESC, length(n.path), n.path
         LIMIT 1) AS target_id
FROM links l;
"""


def index_path_for(vault: Path, storage: Path) -> Path:
    """storage/index/<first 16 hex chars of sha256(absolute vault path)>.sqlite3"""
    digest = hashlib.sha256(str(vault.resolve()).encode()).hexdigest()[:16]
    return storage / "index" / f"{digest}.sqlite3"


def content_hash(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=16).hexdigest()


@dataclass(frozen=True, slots=True)
class NoteState:
    mtime_ns: int
    size: int
    content_hash: str


class Store:
    """One connection, guarded by a lock so the watcher's writer thread and readers can share it."""

    def __init__(self, db_path: Path, vault_root: Path) -> None:
        self.db_path = db_path
        self.vault_root = str(vault_root.resolve())
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self.rebuilt = False
        self._open()

    # -- lifecycle ---------------------------------------------------------

    def _open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = self._connect()
            if self._is_current(conn):
                self._conn = conn
                self.rebuilt = False
                return
            conn.close()
            logger.info("Index %s is missing or out of date; rebuilding", self.db_path)
        except sqlite3.DatabaseError as exc:
            logger.warning("Index %s is unreadable (%s); rebuilding", self.db_path, exc)
        self._delete_files()
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [("schema_version", str(SCHEMA_VERSION)), ("vault_root", self.vault_root)],
        )
        self._conn = conn
        self.rebuilt = True

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _is_current(self, conn: sqlite3.Connection) -> bool:
        has_meta = conn.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'meta'"
        ).fetchone()
        if not has_meta:
            return False
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        return meta.get("schema_version") == str(SCHEMA_VERSION) and (
            meta.get("vault_root") == self.vault_root
        )

    def _delete_files(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self.db_path}{suffix}").unlink(missing_ok=True)

    def reopen_if_deleted(self) -> bool:
        """Reopen (and so rebuild) if the index file was deleted while open."""
        with self._lock:
            if self.db_path.exists():
                return False
            logger.info("Index %s was deleted; rebuilding", self.db_path)
            self.close()
            self._open()
            return True

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store is closed")
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self.conn
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    # -- writes ------------------------------------------------------------

    def upsert_note(self, note: NoteFile, digest: str, parsed: ParsedNote) -> None:
        path = PurePosixPath(note.path)
        with self.transaction() as conn:
            (note_id,) = conn.execute(
                """
                INSERT INTO notes (path, path_key, name_key, title, mtime_ns, size,
                                   content_hash, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (path) DO UPDATE SET
                    path_key = excluded.path_key, name_key = excluded.name_key,
                    title = excluded.title, mtime_ns = excluded.mtime_ns,
                    size = excluded.size, content_hash = excluded.content_hash,
                    indexed_at = excluded.indexed_at
                RETURNING id
                """,
                (
                    note.path,
                    normalize_target(note.path),
                    normalize_target(path.name),
                    parsed.title,
                    note.mtime_ns,
                    note.size,
                    digest,
                    time.time_ns(),
                ),
            ).fetchone()
            conn.execute("DELETE FROM links WHERE source_id = ?", (note_id,))
            conn.execute("DELETE FROM tags WHERE note_id = ?", (note_id,))
            conn.executemany(
                "INSERT INTO links (source_id, target_raw, target_key, alias, heading, is_embed,"
                " line) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (note_id, k.target_raw, k.target_key, k.alias, k.heading, k.is_embed, k.line)
                    for k in parsed.links
                ],
            )
            conn.executemany(
                "INSERT INTO tags (note_id, tag, tag_key, source) VALUES (?, ?, ?, ?)",
                [(note_id, t.tag, t.tag_key, t.source) for t in parsed.tags],
            )

    def update_stat(self, path: str, mtime_ns: int, size: int) -> None:
        """Record a new mtime and size for a note whose content did not change."""
        with self.transaction() as conn:
            conn.execute(
                "UPDATE notes SET mtime_ns = ?, size = ? WHERE path = ?", (mtime_ns, size, path)
            )

    def delete_note(self, path: str) -> bool:
        with self.transaction() as conn:
            return conn.execute("DELETE FROM notes WHERE path = ?", (path,)).rowcount > 0

    def delete_under(self, folder: str) -> int:
        """Delete every note under a vault-relative folder (for folders moved or removed)."""
        prefix = folder.rstrip("/") + "/"
        with self.transaction() as conn:
            return conn.execute(
                "DELETE FROM notes WHERE substr(path, 1, ?) = ?", (len(prefix), prefix)
            ).rowcount

    # -- reads -------------------------------------------------------------

    def _all(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    def note_states(self) -> dict[str, NoteState]:
        rows = self._all("SELECT path, mtime_ns, size, content_hash FROM notes")
        return {str(p): NoteState(int(m), int(s), str(h)) for p, m, s, h in rows}

    def note_title(self, path: str) -> str | None:
        rows = self._all("SELECT title FROM notes WHERE path = ?", (path,))
        return str(rows[0][0]) if rows else None

    def outgoing(self, path: str) -> list[tuple[str, str | None]]:
        """(target as written, resolved target path or None if dangling), in file order."""
        rows = self._all(
            """
            SELECT r.target_raw, t.path FROM resolved_links r
            JOIN notes s ON s.id = r.source_id
            LEFT JOIN notes t ON t.id = r.target_id
            WHERE s.path = ? ORDER BY r.line, r.link_id
            """,
            (path,),
        )
        return [(str(raw), None if t is None else str(t)) for raw, t in rows]

    def backlinks(self, path: str) -> list[str]:
        rows = self._all(
            """
            SELECT DISTINCT s.path FROM resolved_links r
            JOIN notes s ON s.id = r.source_id
            JOIN notes t ON t.id = r.target_id
            WHERE t.path = ? ORDER BY s.path
            """,
            (path,),
        )
        return [str(p) for (p,) in rows]

    def tagged(self, tag: str) -> list[str]:
        rows = self._all(
            "SELECT DISTINCT n.path FROM tags g JOIN notes n ON n.id = g.note_id"
            " WHERE g.tag_key = ? ORDER BY n.path",
            (tag.removeprefix("#").casefold(),),
        )
        return [str(p) for (p,) in rows]

    def counts(self) -> dict[str, int]:
        (row,) = self._all(
            """
            SELECT (SELECT count(*) FROM notes),
                   (SELECT count(*) FROM links),
                   (SELECT count(*) FROM resolved_links WHERE target_id IS NULL),
                   (SELECT count(*) FROM tags),
                   (SELECT count(DISTINCT tag_key) FROM tags)
            """
        )
        keys = ("notes", "links", "dangling_links", "tags", "distinct_tags")
        return {k: int(v) for k, v in zip(keys, row, strict=True)}

    def snapshot(self) -> dict[str, list[tuple[object, ...]]]:
        """Everything except ids and timestamps, for comparing two builds."""
        return {
            "notes": self._all(
                "SELECT path, path_key, name_key, title, size, content_hash"
                " FROM notes ORDER BY path"
            ),
            "links": self._all(
                """
                SELECT s.path, r.target_raw, r.target_key, r.alias, r.heading, r.is_embed,
                       r.line, t.path
                FROM resolved_links r JOIN notes s ON s.id = r.source_id
                LEFT JOIN notes t ON t.id = r.target_id
                ORDER BY s.path, r.line, r.target_raw
                """
            ),
            "tags": self._all(
                "SELECT n.path, g.tag, g.tag_key, g.source FROM tags g"
                " JOIN notes n ON n.id = g.note_id ORDER BY n.path, g.tag_key, g.source"
            ),
        }
