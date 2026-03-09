from typing import Set, Any

from mongoose.core import Singleton


class JobRegistry(metaclass=Singleton):
    def __init__(self):
        self.jobs: Set[Any] = set()

    def register(self, job: Any):
        self.jobs.add(job)

    def clear(self):
        self.jobs.clear()
