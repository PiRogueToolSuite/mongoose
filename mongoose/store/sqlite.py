# SPDX-FileCopyrightText: 2026 Defensive Lab Agency
# SPDX-FileContributor: u039b <git@0x39b.fr>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading
from pathlib import Path
from typing import Dict, Type

from sqlalchemy import create_engine, Table
from sqlalchemy.orm import sessionmaker

from mongoose.store.history import SqliteHistoryManager
from mongoose.models.configuration import HistoryConfiguration
from mongoose.core.processing import ProcessingQueue, ProcessingTopic
from mongoose.models import (
    Base,
    NetworkAlert,
    NetworkAlertTable,
    NetworkFlow,
    NetworkFlowTable,
    NetworkDPI,
    NetworkDPITable,
)

logger = logging.getLogger(__name__)


class SqliteStore:
    """Storage implementation for SQLite database.

    Subscribes to all topics and persists data using SQLAlchemy models.
    """

    def __init__(self, db_path: Path = Path("mongoose.db"), history_config: HistoryConfiguration = None):
        """Initialize the SqliteStore.

        Args:
            db_path: Path to the SQLite database file. Defaults to "mongoose.db".
            history_config: Configuration for history limiting.
        """
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.Session = sessionmaker(bind=self.engine)
        self.processing_queue = ProcessingQueue()
        self.thread = None
        self.history_manager = SqliteHistoryManager(self.Session, history_config or HistoryConfiguration())

        # Map topics to their respective Pydantic and SQLAlchemy models
        self.model_map: Dict[ProcessingTopic, Dict[str, Type[Table]]] = {
            ProcessingTopic.NETWORK_ALERT: {
                "pydantic": NetworkAlert,
                "table": NetworkAlertTable,
            },
            ProcessingTopic.NETWORK_FLOW: {
                "pydantic": NetworkFlow,
                "table": NetworkFlowTable,
            },
            ProcessingTopic.NETWORK_DPI: {
                "pydantic": NetworkDPI,
                "table": NetworkDPITable,
            },
            ProcessingTopic.ENRICHED_NETWORK_ALERT: {
                "pydantic": NetworkAlert,
                "table": NetworkAlertTable,
            },
            ProcessingTopic.ENRICHED_NETWORK_FLOW: {
                "pydantic": NetworkFlow,
                "table": NetworkFlowTable,
            },
            ProcessingTopic.ENRICHED_NETWORK_DPI: {
                "pydantic": NetworkDPI,
                "table": NetworkDPITable,
            },
        }
        self.queue = None
        self._create_tables()

    def _create_tables(self):
        """Create database tables based on defined models."""
        logger.info("Creating SQLite tables if they do not exist")
        Base.metadata.create_all(self.engine)

    def start(self):
        """Start the storage worker thread.

        This method launches a background daemon thread that runs the `_run` loop
        to process and persist data from the subscribed topics.
        """
        if self.thread and self.thread.is_alive():
            return

        # Subscribe early to ensure topics exist before start() returns
        topics = list(self.model_map.keys())
        self.queue = self.processing_queue.subscribe(topics, subscriber_id="sqlite_store")

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("SqliteStore worker thread started")

    def _run(self):
        """Main worker loop to process messages from all topics.

        Continuously polls the queue for new data. Each received item is passed
        to `_save_data` for persistence.
        The loop terminates when `processing_stopped()` returns True.
        """
        while not self.processing_queue.processing_stopped():
            try:
                # Use a timeout to occasionally check if processing has stopped
                data = self.queue.get(timeout=1.0)
                if data is None:
                    self.queue.task_done()
                    continue

                self._save_data(data)
                self.queue.task_done()
            except Exception as e:
                import queue as q

                if isinstance(e, q.Empty):
                    continue
                logger.error(f"Error in SqliteStore worker: {e}")

    def _save_data(self, data: any):
        """Identify data type and save it to the database.

        Orchestrates the persistence process by mapping the input data to target models,
        converting it to a dictionary, and then persisting it.

        Args:
            data: The Pydantic model instance received from a topic.
        """
        target_models = self._get_target_models(data)
        if not target_models:
            logger.warning(f"Received unknown data type in SqliteStore: {type(data)}")
            return

        data_dict = self._model_to_dict(data)
        self._persist_record(target_models["table"], data_dict)

    def _get_target_models(self, data: any) -> Dict[str, Type[Table]] | None:
        """Determine topic and models based on data type.

        Args:
            data: The data object to identify.

        Returns:
            A dictionary containing the "pydantic" and "table" classes if found,
            None otherwise.
        """
        for models in self.model_map.values():
            if isinstance(data, models["pydantic"]):
                return models
        return None

    def _model_to_dict(self, data: any) -> dict:
        """Convert Pydantic model to dict, handling version differences and extra fields.

        Handles Pydantic v1 (`.dict()`) and v2 (`.model_dump()`) compatibility.
        Also ensures that specific properties like `community_id_b64` are included
        in the resulting dictionary if present on the model.

        Args:
            data: The Pydantic model instance to convert.

        Returns:
            A dictionary representation of the model data.
        """
        # Pydantic v1 uses .dict(), v2 uses .model_dump()
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump()
        else:
            data_dict = data.dict()

        # Remove Pydantic internal fields if they leaked into dict
        data_dict.pop("model_config", None)

        # Add extra fields that might be properties in Pydantic but needed in DB
        if hasattr(data, "community_id_b64"):
            data_dict["community_id_b64"] = data.community_id_b64

        return data_dict

    def _persist_record(self, table_class: Type[Table], data_dict: dict):
        """Persist a record to the database.

        Args:
            table_class: The SQLAlchemy model class (table) to instantiate.
            data_dict: The data to populate the record with.
        """
        try:
            with self.Session() as session:
                record = table_class(**data_dict)
                instance = session.query(table_class).filter_by(id=data_dict["id"]).first()
                if instance:
                    # Update
                    for k, v in data_dict.items():
                        setattr(instance, k, v)
                    session.commit()
                else:
                    # Create
                    session.add(record)
                    session.commit()

            # After successful persistence, trigger cleanup
            self.history_manager.cleanup(table_class)
        except Exception as e:
            logger.error(f"Failed to save data to SQLite: {e}")
