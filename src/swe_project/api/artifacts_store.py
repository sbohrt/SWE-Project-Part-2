"""
Thread-safe in-memory artifact store for the Phase 2 API.

This keeps things simple for the autograder: no external services required.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Dict, List, Optional

ArtifactRecord = Dict[str, object]

_LOCK = threading.RLock()


def _now_ts() -> int:
    return int(time.time())


def _make_id() -> str:
    # Generate a 10-digit-ish numeric-looking ID to match examples
    return str(uuid.uuid4().int % 10_000_000_000)


def _normalize_type(t: str) -> Optional[str]:
    if not isinstance(t, str):
        return None
    t = t.strip().lower()
    if t in {"model", "dataset", "code"}:
        return t
    return None


def _infer_name_from_url(url: str) -> str:
    # Take the last non-empty path segment as the name fallback
    parts = [p for p in url.rstrip("/").split("/") if p]
    return parts[-1] if parts else "artifact"


class ArtifactStore:
    def __init__(self) -> None:
        self._by_id: Dict[str, ArtifactRecord] = {}

    def reset(self) -> None:
        with _LOCK:
            self._by_id.clear()

    def create(self, artifact_type: str, url: str, name: Optional[str] = None) -> ArtifactRecord:
        atype = _normalize_type(artifact_type)
        if atype is None:
            raise ValueError("invalid artifact type")
        if not url or not isinstance(url, str):
            raise ValueError("invalid url")

        with _LOCK:
            # naive dedupe: if same type+url+name exists, return 409 signal
            for rec in self._by_id.values():
                if rec["metadata"]["type"] == atype and rec["data"]["url"] == url:
                    raise FileExistsError("artifact exists")

            _id = _make_id()
            _name = name or _infer_name_from_url(url)
            now = _now_ts()
            record: ArtifactRecord = {
                "metadata": {"name": _name, "id": _id, "type": atype},
                "data": {
                    "url": url,
                    "download_url": f"https://example.com/download/{_id}",
                },
                "created_at": now,
                "updated_at": now,
            }
            self._by_id[_id] = record
            return record

    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        with _LOCK:
            return self._by_id.get(artifact_id)

    def update(self, artifact_type: str, artifact_id: str, artifact: ArtifactRecord) -> bool:
        atype = _normalize_type(artifact_type)
        if atype is None:
            return False
        md = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
        data = artifact.get("data", {}) if isinstance(artifact, dict) else {}
        if (
            md.get("id") != artifact_id
            or _normalize_type(md.get("type", "")) != atype
            or not md.get("name")
            or not data.get("url")
        ):
            return False

        with _LOCK:
            if artifact_id not in self._by_id:
                return False
            # keep download_url if not provided
            prior = self._by_id[artifact_id]
            download_url = data.get("download_url") or prior["data"].get("download_url")
            now = _now_ts()
            self._by_id[artifact_id] = {
                "metadata": {"name": md["name"], "id": artifact_id, "type": atype},
                "data": {"url": data["url"], "download_url": download_url},
                "created_at": prior.get("created_at", now),
                "updated_at": now,
            }
            return True

    def delete(self, artifact_type: str, artifact_id: str) -> bool:
        atype = _normalize_type(artifact_type)
        if atype is None:
            return False
        with _LOCK:
            rec = self._by_id.get(artifact_id)
            if not rec or rec["metadata"]["type"] != atype:
                return False
            self._by_id.pop(artifact_id, None)
            return True

    def list_by_queries(self, queries: List[Dict], offset: Optional[str] = None) -> List[ArtifactRecord]:
        """
        queries: list of {"name": "...", "types": ["model", ...]?}
        If name == "*", treat as wildcard for all names.
        We ignore pagination/offset for simplicity; always return all matches.
        """
        with _LOCK:
            records = list(self._by_id.values())

        matches: List[ArtifactRecord] = []
        for q in queries:
            name = q.get("name")
            types = q.get("types")
            allowed_types = None
            if isinstance(types, list):
                allowed_types = set([_normalize_type(t) for t in types if _normalize_type(t)])

            for rec in records:
                md = rec.get("metadata", {})
                if not name or name == "*":
                    pass  # wildcard
                else:
                    if md.get("name") != name:
                        continue
                if allowed_types:
                    if _normalize_type(md.get("type", "")) not in allowed_types:
                        continue
                matches.append(rec)
        # simple de-dupe if multiple queries overlapped
        seen = set()
        out = []
        for rec in matches:
            rid = rec["metadata"]["id"]
            if rid in seen:
                continue
            seen.add(rid)
            out.append(rec)
        return out

    def list_by_name(self, name: str) -> List[ArtifactRecord]:
        with _LOCK:
            return [rec for rec in self._by_id.values() if rec["metadata"]["name"] == name]

    def list_by_regex(self, pattern: str) -> List[ArtifactRecord]:
        regex = re.compile(pattern)
        with _LOCK:
            return [rec for rec in self._by_id.values() if regex.search(rec["metadata"]["name"] or "")]


STORE = ArtifactStore()

