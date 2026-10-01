import json
from ssm.report import write_outputs

def test_safe_to_act_false_when_no_a_candidates(tmp_path):
    write_outputs([], {"max_candidates": 5, "_sec_discovery_mode": "atom"}, tmp_path)
    quality = json.loads((tmp_path / "quality.json").read_text())
    assert quality["SAFE_TO_ACT"] is False
