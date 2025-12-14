# simple in-memory store with a tiny snapshot to /tmp so warm lambdas keep state
import json
import os
import threading
import time
import uuid

_SNAPSHOT = "/tmp/model_store.json"
_LOCK = threading.RLock()


class InMemoryStore:
    def __init__(self):
        self._by_id = {}
        self._jobs = {}
        self._load()

    def _load(self):
        if os.path.exists(_SNAPSHOT):
            try:
                with open(_SNAPSHOT, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._by_id = data.get("by_id", {})
                self._jobs = data.get("jobs", {})
            except Exception:
                self._by_id = {}
                self._jobs = {}

    def _save(self):
        try:
            with open(_SNAPSHOT, "w", encoding="utf-8") as f:
                json.dump({"by_id": self._by_id, "jobs": self._jobs}, f)
        except Exception:
            pass

    # basic CRUD
    def create(self, item):
        with _LOCK:
            _id = item.get("id") or str(uuid.uuid4())
            now = int(time.time())
            item.update({"id": _id, "created_at": now, "updated_at": now})
            self._by_id[_id] = item
            self._save()
            return _id

    def list(self):
        with _LOCK:
            return list(self._by_id.values())

    def get(self, _id):
        with _LOCK:
            return self._by_id.get(_id)

    def update(self, _id, patch):
        with _LOCK:
            if _id not in self._by_id:
                return False
            self._by_id[_id].update(patch)
            self._by_id[_id]["updated_at"] = int(time.time())
            self._save()
            return True

    def delete(self, _id):
        with _LOCK:
            ok = self._by_id.pop(_id, None) is not None
            if ok:
                self._save()
            return ok

    # light job registry (useful for ingest later)
    def job_create(self, payload):
        with _LOCK:
            jid = str(uuid.uuid4())
            self._jobs[jid] = {
                "job_id": jid,
                "status": "queued",
                "payload": payload,
                "result": None,
            }
            self._save()
            return jid

    def job_set(self, job_id, status, result=None):
        with _LOCK:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = status
                self._jobs[job_id]["result"] = result
                self._save()

    def job_get(self, job_id):
        with _LOCK:
            return self._jobs.get(job_id)


STORE = InMemoryStore()
