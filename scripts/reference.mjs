const MIN_SPAN = 3;
const MAX_SEGMENTS = 4;

function gcd(a, b) {
  while (b) [a, b] = [b, a % b];
  return a < 0n ? -a : a;
}

function rational(num, den) {
  const divisor = gcd(num, den);
  return [num / divisor, den / divisor];
}

function add([a, b], [c, d]) {
  return rational(a * d + c * b, b * d);
}

function less([a, b], [c, d]) {
  return a * d < c * b;
}

function numeric(pair) {
  return pair.map(value => {
    const result = Number(value);
    if (!Number.isSafeInteger(result)) throw new RangeError("Unsafe proof integer");
    return result;
  });
}

function segment(observations, start, end) {
  const values = observations.slice(start, end).map(row => BigInt(row[1]));
  const n = BigInt(values.length);
  const sum = values.reduce((total, value) => total + value, 0n);
  const error = values.reduce((total, value) => total + (n * value - sum) ** 2n, 0n);
  return {
    loss: rational(error, n ** 2n),
    interval: {
      start_year: observations[start][0],
      end_year: observations[end - 1][0],
      mean_centi_c: numeric(rational(sum, n)),
    },
  };
}

function* partitions(length, remaining, start = 0) {
  if (remaining === 1) {
    yield [length];
    return;
  }
  for (let end = start + MIN_SPAN; end <= length - (remaining - 1) * MIN_SPAN; end++) {
    for (const suffix of partitions(length, remaining - 1, end)) yield [end, ...suffix];
  }
}

export function fitReference(observations) {
  const result = [];
  for (let count = 1; count <= MAX_SEGMENTS; count++) {
    let best;
    for (const ends of partitions(observations.length, count)) {
      const spans = ends.map((end, index) => segment(observations, ends[index - 1] ?? 0, end));
      const loss = spans.reduce((total, part) => add(total, part.loss), [0n, 1n]);
      if (!best || less(loss, best.loss)) {
        best = { loss, segments: spans.map(part => part.interval) };
      }
    }
    result.push({ segments: best.segments, squared_error_centi_c2: numeric(best.loss) });
  }
  return result;
}

export function chooseReference(models, penalty) {
  let best;
  for (const [index, model] of models.entries()) {
    const loss = model.squared_error_centi_c2.map(BigInt);
    const score = add(loss, [BigInt(penalty) * BigInt(index), 1n]);
    if (!best || less(score, best.score)) best = { score, index };
  }
  return { segment_count: best.index + 1, score_centi_c2: numeric(best.score), ...models[best.index] };
}
