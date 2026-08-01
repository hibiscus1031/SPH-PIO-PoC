from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source  # noqa: E402


def test_source_is_pure_and_preserves_input_graph() -> None:
    positions = torch.tensor([[0.1, 0.2], [-0.3, 0.4]], dtype=torch.float64, requires_grad=True)
    before = positions.detach().clone()
    first = evaluate_mms_source("MMS_B", positions, 0.01)
    second = evaluate_mms_source("MMS_B", positions, 0.01)
    assert torch.equal(positions.detach(), before)
    assert torch.equal(first, second)
    assert first.data_ptr() != second.data_ptr()
    assert first.requires_grad
