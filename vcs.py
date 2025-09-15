import os
import json
import time
from datetime import datetime
from pathlib import Path
from .utils import sha1_file, sha1_bytes

VCS_DIR = ".pyvcs"
BLOBS_DIR = "blobs"
MANIFESTS_DIR = "manifests"
HEAD_FILE = "HEAD"

class Repo:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.vcs_path = self.root / VCS_DIR
        self.blobs = self.vcs_path / BLOBS_DIR
        self.manifests = self.vcs_path / MANIFESTS_DIR
        self.head = self.vcs_path / HEAD_FILE

    def exists(self):
        return self.vcs_path.exists()

    def init(self):
        if self.exists():
            return
        self.vcs_path.mkdir(parents=True)
        self.blobs.mkdir()
        self.manifests.mkdir()
        self.head.write_text("")
        self.snapshot(message="Initial snapshot")

    def _is_ignored(self, p: Path) -> bool:
        return VCS_DIR in p.parts

    def _collect_files(self):
        files = {}
        for root, dirs, filenames in os.walk(self.root):
            rp = Path(root)
            if self._is_ignored(rp):
                dirs[:] = []
                continue
            for fname in filenames:
                p = rp / fname
                if self._is_ignored(p):
                    continue
                rel = str(p.relative_to(self.root)).replace("\\", "/")
                try:
                    h = sha1_file(p)
                    size = p.stat().st_size
                    files[rel] = {"hash": h, "size": size}
                except Exception:
                    continue
        return files

    def _fingerprint_for_files(self, files_map: dict) -> str:
        files_only = {k: v["hash"] for k, v in sorted(files_map.items())}
        return sha1_bytes(json.dumps(files_only, sort_keys=True).encode())

    def snapshot(self, message: str = ""):
        files = self._collect_files()
        fingerprint = self._fingerprint_for_files(files)
        current_head = self.head.read_text().strip() if self.head.exists() else ""
        if current_head == fingerprint:
            return fingerprint, False
        manifest = {
            "fingerprint": fingerprint,
            "time": time.time(),
            "iso": datetime.utcnow().isoformat() + "Z",
            "message": message,
            "files": files,
        }
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        manifest_name = f"{fingerprint}-{ts}.json"
        (self.manifests / manifest_name).write_text(json.dumps(manifest, indent=2))
        for rel, info in files.items():
            h = info.get("hash")
            blob_path = self.blobs / h
            if not blob_path.exists():
                src = self.root / rel
                try:
                    blob_path.write_bytes(src.read_bytes())
                except Exception:
                    pass
        self.head.write_text(fingerprint)
        return fingerprint, True

    def list_snapshots(self):
        if not self.manifests.exists():
            return []
        items = []
        for p in self.manifests.iterdir():
            if p.is_file() and p.suffix == '.json':
                try:
                    data = json.loads(p.read_text())
                    items.append((p.name, data))
                except Exception:
                    continue
        items.sort(key=lambda x: x[1]['time'])
        print(f"Listed {len(items)} snapshots")  # Debug
        return items

    def load_manifest(self, name: str):
        return json.loads((self.manifests / name).read_text())

    def read_blob(self, hash_id: str) -> bytes:
        p = self.blobs / hash_id
        return p.read_bytes() if p.exists() else b""
