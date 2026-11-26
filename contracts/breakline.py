# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from fractions import Fraction
import hashlib
import json
import re

from genlayer import *


SOURCE_PREFIX = "https://raw.githubusercontent.com/datasets/global-temp/"
INDICATOR = "GISTEMP"
YEARS = range(2000, 2024)
MIN_SPAN = 3
MAX_SEGMENTS = 4


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_series(body, source):
    lines = body.decode("utf-8").splitlines()
    if not lines or lines[0] != "Source,Year,Mean":
        raise ValueError("Unexpected temperature data columns")
    observations = {}
    for line in lines[1:]:
        label, year, value = line.split(",")
        if label != INDICATOR:
            continue
        if not re.fullmatch(r"[0-9]{4}", year):
            raise ValueError("Invalid year")
        year = int(year)
        if year not in YEARS:
            continue
        if year in observations or not re.fullmatch(r"-?[0-9](?:\.[0-9]{1,10})?", value):
            raise ValueError("Duplicate or invalid annual anomaly")
        anomaly = Fraction(value)
        if not -5 <= anomaly <= 5:
            raise ValueError("Anomaly out of range")
        observations[year] = round(100 * anomaly)
    if len(observations) != len(YEARS):
        raise ValueError("Expected all 24 annual observations")
    return {
        "source": source,
        "indicator": INDICATOR,
        "observations": [[year, observations[year]] for year in YEARS],
    }


def acquire(source):
    def observe():
        try:
            response = gl.nondet.web.get(source)
            if response.status != 200 or not 1 <= len(response.body) <= 16_384:
                raise ValueError("Invalid temperature data response")
            return canonical(parse_series(response.body, source))
        except Exception:
            raise gl.vm.UserError("Temperature series acquisition failed")

    def validate(leader):
        if not isinstance(leader, gl.vm.Return):
            return False
        try:
            return observe() == leader.calldata
        except Exception:
            return False

    return gl.vm.run_nondet_unsafe(observe, validate)


def ratio(value):
    return [value.numerator, value.denominator]


def fit_models(observations):
    count = len(observations)
    sums, squares = [0], [0]
    for _, value in observations:
        sums.append(sums[-1] + value)
        squares.append(squares[-1] + value * value)

    def average(start, end):
        return Fraction(sums[end] - sums[start], end - start)

    def loss(start, end):
        return squares[end] - squares[start] - average(start, end) ** 2 * (end - start)

    # For each reachable length, retain the exact cost and earliest cut vector.
    previous = {0: (Fraction(0), ())}
    models = []
    for segments in range(1, min(MAX_SEGMENTS, count // MIN_SPAN) + 1):
        current = {}
        for end in range(segments * MIN_SPAN, count + 1):
            candidates = (
                (score + loss(start, end), cuts + (end,))
                for start, (score, cuts) in previous.items() if end - start >= MIN_SPAN
            )
            best = min(candidates, default=None)
            if best is not None:
                current[end] = best
        score, ends = current[count]
        starts = (0,) + ends[:-1]
        models.append({
            "segments": [
                {"start_year": observations[start][0], "end_year": observations[end - 1][0],
                 "mean_centi_c": ratio(average(start, end))}
                for start, end in zip(starts, ends)
            ],
            "squared_error_centi_c2": ratio(score),
        })
        previous = current
    return models


class Breakline(gl.Contract):
    studies: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def publish(self, revision: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise gl.vm.UserError("Expected a full upstream commit hash")
        evidence = acquire(SOURCE_PREFIX + revision + "/data/annual.csv")
        study_id = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        if study_id not in self.studies:
            series = json.loads(evidence)
            self.studies[study_id] = canonical({**series, "models": fit_models(series["observations"])})
        return study_id

    @gl.public.view
    def get_study(self, study_id: str) -> dict | None:
        return json.loads(self.studies[study_id]) if study_id in self.studies else None

    @gl.public.view
    def choose(self, study_id: str, penalty_centi_c2: u64) -> dict:
        study = self.get_study(study_id)
        if study is None:
            raise gl.vm.UserError("Unknown study")
        penalty = int(penalty_centi_c2)
        score, index = min(
            (Fraction(*model["squared_error_centi_c2"]) + penalty * index, index)
            for index, model in enumerate(study["models"])
        )
        return {"segment_count": index + 1, "score_centi_c2": ratio(score), **study["models"][index]}
