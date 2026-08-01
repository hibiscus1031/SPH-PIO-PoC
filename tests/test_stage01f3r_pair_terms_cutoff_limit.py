from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.cutoff_smoothness import cutoff_probe

def test_actual_pair_terms_vanish_at_cutoff()->None:
    rows=cutoff_probe();at=next(row for row in rows if row["q"]==1.0);outside=[row for row in rows if row["q"]>1]
    assert at["pressure_pair_l2"]==0 and at["viscosity_pair_l2"]==0
    assert all(row["total_pair_l2"]==0 for row in outside)
    assert rows[3]["acceleration_contribution_l2"]<1e-30
