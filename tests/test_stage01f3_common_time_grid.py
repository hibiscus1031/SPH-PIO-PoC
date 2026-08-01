from pathlib import Path
import sys,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.temporal_self_difference import common_time_grid_identity

def test_common_physical_time_grid_identity()->None:
    grid=np.linspace(0,.02,21)
    assert common_time_grid_identity(grid,grid.copy())
    assert not common_time_grid_identity(grid,grid+1e-6)
