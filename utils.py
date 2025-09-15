import hashlib

CHUNK_SIZE = 1024 * 64


def sha1_file(path):
    """SHA1 hash of a file (streaming)."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            data = f.read(CHUNK_SIZE)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()
