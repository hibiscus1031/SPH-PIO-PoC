from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.support_consistency_path import PATH,path_entry

def test_preregistered_support_path_has_positive_shell_margins()->None:
    assert set(PATH)=={16,24,32,48,64}
    assert all(path_entry(n)["minimum_cutoff_margin"]>1e-12 for n in PATH)
