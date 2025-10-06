from aioreactive import AsyncSubject

_ipc: AsyncSubject | None = None


def create_subject() -> AsyncSubject:
    global _ipc

    if _ipc is None:
        print("Creating subject")
        _ipc = AsyncSubject()

    return _ipc
