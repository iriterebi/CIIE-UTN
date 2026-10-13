import threading
from collections.abc import Callable


class AtomicVar[T]:
    """Valor compartido entre threads: get(), set() y mutate() son atómicos.

    `get()` devuelve una referencia al valor guardado, que el lector usa fuera del
    lock. Por eso el valor debe tratarse como inmutable: para cambiarlo se guarda uno
    nuevo (`set()` o `mutate()`), nunca se modifica el objeto que ya se entregó.

    Para actualizar a partir del valor actual, usar `mutate()`: una secuencia
    get() → modificar → set() suelta el lock entre la lectura y la escritura, y con
    varios escritores pierde actualizaciones.
    """

    def __init__(self, default_value: T) -> None:
        self._value: T = default_value
        self._lock: threading.Lock = threading.Lock()

    def get(self) -> T:
        with self._lock:
            return self._value

    def set(self, val: T) -> None:
        with self._lock:
            self._value = val

    def mutate(self, mutator: Callable[[T], T]) -> None:
        """Reemplaza el valor por `mutator(valor_actual)` sin soltar el lock.

        `mutator` debe devolver un valor nuevo y no modificar el que recibe (ej.
        `lambda d: d | cambios`, no `d.update(cambios)`): los lectores pueden estar
        usando ese objeto fuera del lock. Corre con el lock tomado, así que debe ser
        rápido y no llamar a esta misma instancia.
        """
        with self._lock:
            self._value = mutator(self._value)
