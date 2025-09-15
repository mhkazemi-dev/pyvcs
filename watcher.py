import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class DebouncedHandler(FileSystemEventHandler):
    def __init__(self, repo, callback, debounce_seconds=2.0):
        super().__init__()
        self.repo = repo
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._timer = None
        self._lock = threading.Lock()

    def _schedule(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._do_snapshot)
            self._timer.daemon = True
            self._timer.start()

    def _do_snapshot(self):
        try:
            fingerprint, created = self.repo.snapshot(message="Auto snapshot")
            print(f"Watcher snapshot: fingerprint={fingerprint}, created={created}")  # Debug
            if created:
                import time
                time.sleep(0.2)  # Increased delay for FS sync
                print("Calling callback for UI refresh")  # Debug
                self.callback()
        except Exception as e:
            print("Watcher snapshot error:", e)

    def on_any_event(self, event):
        if ".pyvcs" in str(getattr(event, "src_path", "")):
            return
        print(f"Detected event: type={event.event_type}, path={event.src_path}, is_directory={event.is_directory}")  # Debug
        self._schedule()

class AutoWatcher:
    def __init__(self, repo, callback):
        self.repo = repo
        self.callback = callback
        self.observer = Observer()
        self.handler = DebouncedHandler(repo, callback)

    def start(self):
        self.observer.schedule(self.handler, str(self.repo.root), recursive=True)
        self.observer.start()
        print("Observer started, monitoring:", str(self.repo.root))  # Debug

    def stop(self):
        try:
            self.observer.stop()
            self.observer.join()
        except Exception:
            pass