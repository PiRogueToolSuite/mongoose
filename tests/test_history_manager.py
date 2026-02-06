import os
import time
from datetime import datetime, timedelta

import pytest

from mongoose.store.sqlite import SqliteStore
from mongoose.models import NetworkAlert, NetworkAlertTable
from mongoose.models.configuration import HistoryConfiguration


@pytest.fixture
def db_path():
    path = "test_history.db"
    if os.path.exists(path):
        os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def get_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def test_history_limit_by_size(db_path):
    config = HistoryConfiguration(max_records=5, enable=True)
    store = SqliteStore(db_path=db_path, history_config=config)

    # Add 10 records
    for i in range(10):
        alert = NetworkAlert(
            id=f"alert_{i}",
            flow_id=i,
            src_ip="1.1.1.1",
            src_port=123,
            dst_ip="2.2.2.2",
            dst_port=80,
            protocol="TCP",
            action="allowed",
            gid=1,
            signature_id=1,
            rev=1,
            signature="test",
            category="test",
            severity=1,
            time=datetime.now() + timedelta(seconds=i),  # Ensure different times
        )
        store._persist_record(NetworkAlertTable, get_dict(alert))

    with store.Session() as session:
        count = session.query(NetworkAlertTable).count()
        assert count == 5

        # Check that the remaining records are the latest ones (alert_5 to alert_9)
        remaining_ids = [r.id for r in session.query(NetworkAlertTable).order_by(NetworkAlertTable.time.asc()).all()]
        assert remaining_ids == ["alert_5", "alert_6", "alert_7", "alert_8", "alert_9"]


def test_history_limit_by_duration(db_path):
    # Limit to 1 day
    config = HistoryConfiguration(max_duration_days=1, enable=True)
    store = SqliteStore(db_path=db_path, history_config=config)

    now = datetime.now()

    # Old record (2 days ago)
    old_alert = NetworkAlert(
        id="old",
        flow_id=1,
        src_ip="1.1.1.1",
        src_port=123,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        action="allowed",
        gid=1,
        signature_id=1,
        rev=1,
        signature="test",
        category="test",
        severity=1,
        time=now - timedelta(days=2),
    )

    # New record (now)
    new_alert = NetworkAlert(
        id="new",
        flow_id=2,
        src_ip="1.1.1.1",
        src_port=123,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        action="allowed",
        gid=1,
        signature_id=1,
        rev=1,
        signature="test",
        category="test",
        severity=1,
        time=now,
    )

    # Directly persist without cleanup first to ensure they are both there
    with store.Session() as session:
        session.add(NetworkAlertTable(**get_dict(old_alert)))
        session.add(NetworkAlertTable(**get_dict(new_alert)))
        session.commit()

    # Now trigger cleanup by persisting another record
    another_alert = NetworkAlert(
        id="another",
        flow_id=3,
        src_ip="1.1.1.1",
        src_port=123,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        action="allowed",
        gid=1,
        signature_id=1,
        rev=1,
        signature="test",
        category="test",
        severity=1,
        time=now,
    )
    store._persist_record(NetworkAlertTable, get_dict(another_alert))

    with store.Session() as session:
        count = session.query(NetworkAlertTable).count()
        # Should have "new" and "another". "old" should be gone.
        assert count == 2
        ids = [r.id for r in session.query(NetworkAlertTable).all()]
        assert "old" not in ids
        assert "new" in ids
        assert "another" in ids
