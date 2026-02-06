import logging
from datetime import datetime, timedelta
from typing import Type

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from mongoose.models import Base
from mongoose.models.configuration import HistoryConfiguration

logger = logging.getLogger(__name__)


class SqliteHistoryManager:
    """Manages the size and duration of records in the SQLite database."""

    def __init__(self, session_factory, config: HistoryConfiguration):
        """Initialize the SqliteHistoryManager.

        Args:
            session_factory: A sessionmaker instance.
            config: History limiting configuration.
        """
        self.Session = session_factory
        self.config = config

    def cleanup(self, table_class: Type[Base]):
        """Perform cleanup for the specified table based on configuration.

        Args:
            table_class: The SQLAlchemy model class (table) to clean up.
        """
        if not self.config or not self.config.enable:
            return

        try:
            if self.config.max_duration_days:
                self._cleanup_by_duration(table_class)

            if self.config.max_records:
                self._cleanup_by_size(table_class)
        except Exception as e:
            logger.error(f"Error during database cleanup for {table_class.__tablename__}: {e}")

    def _cleanup_by_duration(self, table_class: Type[Base]):
        """Remove records older than the configured duration.

        Args:
            table_class: The SQLAlchemy model class (table) to clean up.
        """
        cutoff_date = datetime.now() - timedelta(days=self.config.max_duration_days)

        with self.Session() as session:
            # We assume the table has a 'time' column which is a DateTime
            stmt = delete(table_class).where(table_class.time < cutoff_date)
            result = session.execute(stmt)
            session.commit()

            if result.rowcount > 0:
                logger.info(
                    f"Removed {result.rowcount} records from {table_class.__tablename__} "
                    f"older than {self.config.max_duration_days} days"
                )

    def _cleanup_by_size(self, table_class: Type[Base]):
        """Remove older records if the table exceeds the maximum number of records.

        Args:
            table_class: The SQLAlchemy model class (table) to clean up.
        """
        with self.Session() as session:
            count = session.query(func.count(table_class.id)).scalar()

            if count > self.config.max_records:
                to_delete = count - self.config.max_records

                # Find the IDs of the oldest records to delete
                # We order by time (or id if time is same) to remove older records first
                oldest_ids_query = (
                    select(table_class.id).order_by(table_class.time.asc(), table_class.id.asc()).limit(to_delete)
                )
                oldest_ids = session.execute(oldest_ids_query).scalars().all()

                if oldest_ids:
                    delete_stmt = delete(table_class).where(table_class.id.in_(oldest_ids))
                    session.execute(delete_stmt)
                    session.commit()
                    logger.info(
                        f"Removed {len(oldest_ids)} oldest records from {table_class.__tablename__} "
                        f"to respect max_records limit of {self.config.max_records}"
                    )
