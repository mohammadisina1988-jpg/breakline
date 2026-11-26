from fractions import Fraction
from itertools import combinations
from pathlib import Path
import json
import hashlib
import re

import pytest


CONTRACT = "contracts/breakline.py"
REVISION = "b90e8a349acb508d382d40d1cfa393c723bd82ef"
SOURCE = f"https://raw.githubusercontent.com/datasets/global-temp/{REVISION}/data/annual.csv"
BODY = Path("fixtures/global-temp-annual.csv").read_bytes()


@pytest.fixture
def contract(direct_deploy):
    return direct_deploy(CONTRACT, sdk_version="v0.2.16")


def provide(vm, body=BODY):
    vm.mock_web(re.escape(SOURCE), {"status": 200, "body": body})


def exhaustive(series, count):
    def cost(start, end):
        points = [value for _, value in series[start:end]]
        mean = Fraction(sum(points), len(points))
        return sum((value - mean) ** 2 for value in points)

    scores = []
    for cuts in combinations(range(3, len(series) - 2), count - 1):
        spans = list(zip((0,) + cuts, cuts + (len(series),)))
        if all(end - start >= 3 for start, end in spans):
            scores.append((sum(cost(a, b) for a, b in spans), cuts))
    return min(scores)


def test_actual_series_against_exhaustive_partitions(direct_vm, contract, direct_bob):
    provide(direct_vm)
    with direct_vm.prank(direct_bob):
        study_id = contract.publish(REVISION)
    assert direct_vm.run_validator() is True
    study = contract.get_study(study_id)
    series = study["observations"]
    assert (series[0], series[-1], len(series)) == ([2000, 39], [2023, 117], 24)
    assert hashlib.sha256(json.dumps({k: v for k, v in study.items() if k != "models"},
                                    sort_keys=True, separators=(",", ":")).encode()).hexdigest() == study_id
    for count, model in enumerate(study["models"], 1):
        score, cuts = exhaustive(series, count)
        assert Fraction(*model["squared_error_centi_c2"]) == score
        assert tuple(segment["start_year"] - 2000 for segment in model["segments"][1:]) == cuts
    assert contract.choose(study_id, 0)["segment_count"] == 4
    assert contract.choose(study_id, 1_000_000)["segment_count"] == 1
    assert contract.publish(REVISION) == study_id


def test_validator_disagrees_when_normalized_source_changes(direct_vm, contract):
    provide(direct_vm)
    first = contract.publish(REVISION)
    direct_vm.clear_mocks()
    provide(direct_vm, BODY.replace(b"GISTEMP,2000,0.3933", b"GISTEMP,2000,-0.5000"))
    assert direct_vm.run_validator() is False
    second = contract.publish(REVISION)
    assert first != second
    assert contract.choose(first, 1_000_000)["segments"] != contract.choose(second, 1_000_000)["segments"]


@pytest.mark.parametrize("change", [b"", b"GISTEMP,2000,NaN", b"GISTEMP,2001,0.3933"])
def test_missing_nonfinite_or_duplicate_observation_reverts(direct_vm, contract, change):
    provide(direct_vm, BODY.replace(b"GISTEMP,2000,0.3933", change))
    with direct_vm.expect_revert("Temperature series acquisition failed"):
        contract.publish(REVISION)


def test_penalty_and_cut_ties_use_earliest_minimum(direct_vm, contract):
    body = "Source,Year,Mean\n" + "\n".join(f"GISTEMP,{year},0.50" for year in range(2000, 2024))
    provide(direct_vm, body.encode())
    study_id = contract.publish(REVISION)
    assert contract.get_study(study_id)["models"][3]["segments"][1]["start_year"] == 2003
    assert contract.choose(study_id, 0)["segment_count"] == 1
    with direct_vm.expect_revert("Expected a full upstream commit hash"):
        contract.publish("main")
    with direct_vm.expect_revert("Unknown study"):
        contract.choose("0" * 64, 0)
