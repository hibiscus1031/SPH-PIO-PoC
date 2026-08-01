from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"01_solver"))
from manufactured_solutions.convergence_metrics import gci_qualification

def test_nonmonotone_errors_do_not_qualify()->None:
    result=gci_qualification([1.,.8,.9],[2.,2.])
    assert result["qualified"] is False
