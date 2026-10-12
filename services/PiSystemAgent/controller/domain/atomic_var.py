import threading


class AtomicVar[T]:
    _latest_status: T
    _status_lock: threading.Lock = threading.Lock()

    def __init__(self, default_value: T) -> None:
        self._latest_status = default_value

    def get(self):
        with self._status_lock:
            return self._latest_status

    def set(self, val: T):
        with self._status_lock:
            self._latest_status = val
