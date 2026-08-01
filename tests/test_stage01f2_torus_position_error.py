from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from manufactured_solutions.torus_position_error import minimum_image_displacement  # noqa: E402


def test_positive_and_negative_minimum_images() -> None:
    numerical = torch.tensor([[-0.99, 0.99], [0.99, -0.99]], dtype=torch.float64)
    exact = torch.tensor([[0.99, -0.99], [-0.99, 0.99]], dtype=torch.float64)
    delta = minimum_image_displacement(numerical, exact)
    expected = torch.tensor([[0.02, -0.02], [-0.02, 0.02]], dtype=torch.float64)
    assert torch.allclose(delta, expected, atol=2e-16, rtol=0)
