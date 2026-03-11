# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Set, Any

from mongoose.core import Singleton


class JobRegistry(metaclass=Singleton):
    def __init__(self):
        self.jobs: Set[Any] = set()

    def register(self, job: Any):
        self.jobs.add(job)

    def clear(self):
        self.jobs.clear()
