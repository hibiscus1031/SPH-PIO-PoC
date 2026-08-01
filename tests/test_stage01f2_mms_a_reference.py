from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from manufactured_solutions.mms_a_reference import unwrapped_trajectory, wrapped_trajectory  # noqa: E402


def test_mms_a_closed_reference_times_and_boundary_crossing() -> None:
    initial = torch.tensor([[0.99, 0.2], [-0.99, -0.3]], dtype=torch.float64)
    for time in (0.0, 0.01, 0.05, 0.1, 0.2):
        unwrapped = unwrapped_trajectory(initial, time)
        assert torch.equal(unwrapped[:, 1], initial[:, 1])
        assert torch.allclose(unwrapped[:, 0], initial[:, 0] + 0.5 * time, atol=0, rtol=0)
        wrapped = wrapped_trajectory(initial, time)
        assert bool(((wrapped >= -1.0) & (wrapped < 1.0)).all())
    assert wrapped_trajectory(initial, 0.1)[0, 0] < -0.9
