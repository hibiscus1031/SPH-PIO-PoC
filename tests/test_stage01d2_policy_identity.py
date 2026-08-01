from hashlib import sha256
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "06_experiments/stage_01d2_v2_requalification/configs/preregistered_stage01d2_v2.yml").read_text())


def test_frozen_identities_and_tags() -> None:
    for item in CFG["frozen_identity"].values():
        assert sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert subprocess.check_output(("git", "rev-list", "-n", "1", CFG["frozen_stage01dp"]["tag"]), cwd=ROOT, text=True).strip() == CFG["frozen_stage01dp"]["final_evidence_commit"]
    assert CFG["frozen_stage01dp"]["status"] == "POLICY_PASS_ISOLATED_DEFAULT_GC"
