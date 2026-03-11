# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import logging

from mongoose.core.processing import ProcessingQueue, ProcessingTopic

logger = logging.getLogger(__name__)


class Sink:
    def __init__(self):
        self.processing_queue = ProcessingQueue()
        self.stopped = False
        self.queue = None
        self.thread = None
        self.topics = [
            ProcessingTopic.NETWORK_ALERT,
            ProcessingTopic.NETWORK_FLOW,
            ProcessingTopic.NETWORK_DPI,
            ProcessingTopic.ENRICHED_NETWORK_ALERT,
            ProcessingTopic.ENRICHED_NETWORK_FLOW,
            ProcessingTopic.ENRICHED_NETWORK_DPI,
        ]

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.queue = self.processing_queue.subscribe(self.topics, subscriber_id="sink")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stopped:
            try:
                data = self.queue.get(timeout=2)
                if data is None:
                    self.queue.task_done()
                    continue
                logger.debug("Sink received data: %s", data)
                self.queue.task_done()
            except Exception as e:
                import queue as q

                if isinstance(e, q.Empty):
                    continue

    def stop(self):
        self.stopped = True
