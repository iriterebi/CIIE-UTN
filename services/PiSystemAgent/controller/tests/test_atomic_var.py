import threading
import time

from ..domain import AtomicVar


def test_set_y_get():
    var = AtomicVar({"a": "1"})
    var.set({"b": "2"})
    assert var.get() == {"b": "2"}


def test_get_no_espera_el_lock_de_otra_instancia():
    """Cada instancia protege su propio valor: un set() en curso en `a` no debe
    bloquear un get() de `b` (con un lock compartido entre instancias, sí)."""
    a, b = AtomicVar(1), AtomicVar(2)
    got: list[int] = []

    with a._lock:  # simula un set() de `a` en curso
        reader = threading.Thread(target=lambda: got.append(b.get()), daemon=True)
        reader.start()
        reader.join(timeout=1.0)

    assert got == [2]


def test_mutate_no_pierde_actualizaciones_concurrentes():
    """mutate() sostiene el lock durante leer → aplicar → escribir: con varios
    escritores a la vez no se pierde ningún incremento."""
    counter = AtomicVar(0)

    def increment(n: int) -> int:
        time.sleep(0.0005)  # ensancha la ventana entre leer y escribir
        return n + 1

    writers = [
        threading.Thread(target=lambda: [counter.mutate(increment) for _ in range(20)])
        for _ in range(5)
    ]
    for t in writers:
        t.start()
    for t in writers:
        t.join()

    assert counter.get() == 100
