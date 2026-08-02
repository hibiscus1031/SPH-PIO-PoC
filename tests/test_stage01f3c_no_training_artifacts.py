from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f3c_ct2_adjudication"


def test_scope_and_stage_tree_have_no_training_or_label_artifacts():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f3c.yml").read_text())
    scope = config["scope"]
    assert not scope["training_started"]
    assert not scope["labels_generated"]
    assert not scope["stage01f3d_started"]
    assert not scope["stage01g_started"]
    assert not scope["v3_started"]
    assert not scope["stage02_started"]
    forbidden = ("train", "checkpoint", "label", "target")
    assert not [
        path for path in STAGE.rglob("*")
        if path.is_file() and any(token in path.name.lower() for token in forbidden)
    ]
