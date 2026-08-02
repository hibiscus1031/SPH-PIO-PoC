import csv
import hashlib
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment"
TIMES = STAGE / "configs/formal_space_common_times.csv"


def test_21_common_times_are_constructed_from_integer_ticks():
    with TIMES.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 21
    assert [int(row["tick"]) for row in rows] == list(range(21))
    values = [Decimal(row["time"]) for row in rows]
    assert values[0] == Decimal(0)
    assert values[-1] == Decimal("0.02")
    assert all(value == Decimal(tick) / 1000 for tick, value in enumerate(values))
    assert all(values[index + 1] - values[index] == Decimal("0.001") for index in range(20))


def test_common_times_and_amendment_hashes_are_saved():
    with (STAGE / "manifests/stage01f5q_parameter_sha256_manifest.csv").open() as stream:
        rows = {row["category"]: row for row in csv.DictReader(stream)}
    for category in ("horizon_amendment", "common_times"):
        row = rows[category]
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
