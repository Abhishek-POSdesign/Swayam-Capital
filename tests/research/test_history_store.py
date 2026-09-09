"""The research store must never lose data or leave a half-written file.

A multi-hour download that has to be restarted is annoying. A download that
looks complete and is not is a backtest built on a hole, and the whole point of
this project is that a number is real or says so.

Nothing here touches the network, the database or the vault. Every test writes
into a temporary folder pytest hands it.
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from swayam.research.store import HistoryStore


def _bars(start_minute: int, count: int, close: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame({
        "bar_start_utc": [
            datetime(2026, 9, 9, 4, start_minute + i, tzinfo=timezone.utc) for i in range(count)
        ],
        "open": [close] * count,
        "high": [close + 1] * count,
        "low": [close - 1] * count,
        "close": [close] * count,
        "volume": list(range(count)),
    })


@pytest.fixture
def store(tmp_path):
    return HistoryStore(tmp_path)


def test_a_first_write_creates_the_file(store):
    result = store.write_parquet(_bars(0, 5), "nifty", "1m", "2026.parquet")
    assert result.rows == 5
    assert result.rows_added == 5
    assert result.path.exists()
    assert result.bytes_on_disk > 0


def test_a_second_write_merges_rather_than_replaces(store):
    store.write_parquet(_bars(0, 5), "nifty", "1m", "2026.parquet", dedupe_on=["bar_start_utc"])
    result = store.write_parquet(
        _bars(5, 5), "nifty", "1m", "2026.parquet", dedupe_on=["bar_start_utc"]
    )
    assert result.rows == 10
    assert result.rows_added == 5


def test_refetching_the_same_span_repairs_rather_than_duplicates(store):
    """A resumed download re-requests the chunk it died on. That must be safe."""
    store.write_parquet(_bars(0, 5, close=100.0), "nifty", "1m", "2026.parquet",
                        dedupe_on=["bar_start_utc"])
    result = store.write_parquet(_bars(0, 5, close=111.0), "nifty", "1m", "2026.parquet",
                                 dedupe_on=["bar_start_utc"])
    assert result.rows == 5, "the same minutes were stored twice"
    assert result.rows_added == 0
    written = pd.read_parquet(result.path)
    assert set(written["close"]) == {111.0}, "the later fetch must win"


def test_rows_come_back_in_time_order(store):
    store.write_parquet(_bars(10, 5), "nifty", "1m", "2026.parquet",
                        dedupe_on=["bar_start_utc"], sort_on=["bar_start_utc"])
    store.write_parquet(_bars(0, 5), "nifty", "1m", "2026.parquet",
                        dedupe_on=["bar_start_utc"], sort_on=["bar_start_utc"])
    written = pd.read_parquet(store.path_for("nifty", "1m", "2026.parquet"))
    assert written["bar_start_utc"].is_monotonic_increasing


def test_no_temporary_file_is_left_behind(store):
    result = store.write_parquet(_bars(0, 3), "nifty", "1m", "2026.parquet")
    leftovers = list(result.path.parent.glob("*.tmp"))
    assert leftovers == []


def test_an_interrupted_write_leaves_the_previous_file_intact(store, monkeypatch):
    """The reason every write goes through a temporary file and a rename."""
    store.write_parquet(_bars(0, 5, close=100.0), "nifty", "1m", "2026.parquet",
                        dedupe_on=["bar_start_utc"])

    def die(*args, **kwargs):
        raise KeyboardInterrupt("the machine went to sleep")

    monkeypatch.setattr("swayam.research.store.os.replace", die)
    with pytest.raises(KeyboardInterrupt):
        store.write_parquet(_bars(5, 5), "nifty", "1m", "2026.parquet",
                            dedupe_on=["bar_start_utc"])

    survived = pd.read_parquet(store.path_for("nifty", "1m", "2026.parquet"))
    assert len(survived) == 5, "the good file was damaged by a failed write"
    assert set(survived["close"]) == {100.0}


def test_the_manifest_makes_a_download_resumable(store):
    assert store.is_done("nifty", "1m", key="2018-01-01..2018-03-31") is False
    store.record("nifty", "1m", key="2018-01-01..2018-03-31", entry={"rows": 22401})
    assert store.is_done("nifty", "1m", key="2018-01-01..2018-03-31") is True
    assert store.is_done("nifty", "1m", key="2018-04-01..2018-06-30") is False

    entry = store.read_manifest("nifty", "1m")["entries"]["2018-01-01..2018-03-31"]
    assert entry["rows"] == 22401
    assert entry["fetched_at_utc"], "every entry records when it was fetched"


def test_a_corrupt_manifest_does_not_stop_a_download(store):
    store.manifest_path("nifty", "1m").write_text("{not json", encoding="utf-8")
    assert store.read_manifest("nifty", "1m") == {}
    assert store.is_done("nifty", "1m", key="anything") is False
