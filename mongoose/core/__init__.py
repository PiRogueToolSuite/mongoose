import threading
from typing import Dict, Any


class SingletonMeta(type):
    """
    Thread-safe metaclass implementing a per-class singleton.

    Each class that uses this metaclass will only ever have a single
    instance created. The first construction's args/kwargs are used to
    initialize the singleton; later constructions return the same
    instance and ignore new args.
    """

    _instances: Dict[type, Any] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        # Double-checked locking to avoid acquiring the lock every time
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]


class Singleton(type):
    _instances: Dict[type, type] = {}

    def __call__(cls, *args, **kwargs):
        """Control instance creation to ensure singleton behavior.

        Args:
            cls (type): The class being instantiated
            *args: Positional arguments for class initialization
            **kwargs: Keyword arguments for class initialization

        Returns:
            type: The singleton instance of the class

        Note:
            If an instance already exists, ``__init__`` will still be called with
            the provided arguments, but no new instance is created.
        """
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
