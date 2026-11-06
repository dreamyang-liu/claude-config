#!/usr/bin/env python3
"""t-way covering arrays for test cases, and the t-way coverage of rows you already have.

Model (JSON): {"parameters": {"name": [values]}, "forbidden": [{"name": value}]}. A row is
invalid when it matches every assignment of one forbidden entry. Generation is IPOG (Lei et
al., 2007) and deterministic: one model gives one set of rows.

  covering_array.py MODEL --strength 3 [--python]
  covering_array.py MODEL --strength 3 --measure ROWS.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path


def key(value) -> str:
    # Index values by their JSON text, so that true and 1 stay different values.
    return json.dumps(value, sort_keys=True)


class Model:
    def __init__(self, data: dict) -> None:
        parameters = data.get("parameters")
        if not isinstance(parameters, dict) or not parameters:
            raise ValueError("parameters must be a non-empty object")
        self.names = list(parameters)
        self.values = []
        for name in self.names:
            values = parameters[name]
            if not isinstance(values, list) or not values:
                raise ValueError(f"{name}: needs a non-empty list of values")
            if len({key(v) for v in values}) != len(values):
                raise ValueError(f"{name}: a value occurs twice")
            self.values.append(values)
        self.forbidden = [self.encode(entry, "forbidden") for entry in data.get("forbidden", [])]

    def encode(self, assignment: dict, where: str) -> dict[int, int]:
        """``{name: value}`` as ``{parameter position: value index}``."""
        encoded = {}
        for name, value in assignment.items():
            if name not in self.names:
                raise ValueError(f"{where}: unknown parameter {name!r}")
            p = self.names.index(name)
            keys = [key(v) for v in self.values[p]]
            if key(value) not in keys:
                raise ValueError(f"{where}: {name}={value!r} is not a value of {name}")
            encoded[p] = keys.index(key(value))
        return encoded

    def decode(self, row: list[int]) -> dict:
        return {name: self.values[p][row[p]] for p, name in enumerate(self.names)}

    def violates(self, row: list) -> bool:
        return any(all(row[p] == v for p, v in entry.items()) for entry in self.forbidden)

    def complete(self, row: list) -> list | None:
        """``row`` with each ``None`` filled so that no forbidden entry matches, or ``None``."""
        row = list(row)
        holes = [p for p, v in enumerate(row) if v is None]

        def fill(j: int) -> bool:
            if j == len(holes):
                return True
            for v in range(len(self.values[holes[j]])):
                row[holes[j]] = v
                if not self.violates(row) and fill(j + 1):
                    return True
            row[holes[j]] = None
            return False

        return row if not self.violates(row) and fill(0) else None

    def feasible(self, combo: tuple) -> bool:
        row = [None] * len(self.names)
        for p, v in combo:
            row[p] = v
        return self.complete(row) is not None


def combos_with(model: Model, params: list[int], strength: int):
    """Every t-way combination over ``params``, as sorted ``((position, value), ...)``."""
    for subset in itertools.combinations(sorted(params), strength):
        for values in itertools.product(*(range(len(model.values[p])) for p in subset)):
            yield tuple(zip(subset, values))


def covered_by(row: list, new: int, earlier: list[int], strength: int):
    """The combinations that ``row`` covers and that include parameter ``new``."""
    if row[new] is None:
        return
    assigned = [p for p in earlier if row[p] is not None]
    for subset in itertools.combinations(assigned, strength - 1):
        yield tuple(sorted([(p, row[p]) for p in subset] + [(new, row[new])]))


def generate(model: Model, strength: int) -> list[list[int]]:
    k = len(model.names)
    strength = min(strength, k)
    # IPOG: the largest domains first, so that the exhaustive start is the costly part.
    order = sorted(range(k), key=lambda p: -len(model.values[p]))
    rows = []
    for combo in combos_with(model, order[:strength], strength):
        row = [None] * k
        for p, v in combo:
            row[p] = v
        if model.complete(row) is not None:
            rows.append(row)
    for i in range(strength, k):
        new, earlier = order[i], order[:i]
        uncovered = {c for c in combos_with(model, earlier + [new], strength)
                     if any(p == new for p, _ in c) and model.feasible(c)}
        for row in rows:  # horizontal growth
            best, gain = None, 0
            for v in range(len(model.values[new])):
                row[new] = v
                if model.complete(row) is None:
                    continue
                count = sum(1 for c in covered_by(row, new, earlier, strength) if c in uncovered)
                if count > gain:
                    best, gain = v, count
            row[new] = best
            uncovered.difference_update(covered_by(row, new, earlier, strength))
        for combo in sorted(uncovered):  # vertical growth
            if combo not in uncovered:
                continue
            target = None
            for row in rows:
                if all(row[p] is None or row[p] == v for p, v in combo):
                    trial = list(row)
                    for p, v in combo:
                        trial[p] = v
                    if model.complete(trial) is not None:
                        row[:] = trial
                        target = row
                        break
            if target is None:
                target = [None] * k
                for p, v in combo:
                    target[p] = v
                rows.append(target)
            uncovered.difference_update(covered_by(target, new, earlier, strength))
    return [model.complete(row) for row in rows]


def measure(model: Model, rows: list[list[int]], strength: int) -> tuple[int, list[tuple]]:
    """The number of feasible t-way combinations, and the ones that no row covers."""
    strength = min(strength, len(model.names))
    seen = set()
    for row in rows:
        seen.update(itertools.combinations(tuple(enumerate(row)), strength))
    feasible = [c for c in combos_with(model, list(range(len(model.names))), strength)
                if model.feasible(c)]
    return len(feasible), [c for c in feasible if c not in seen]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", type=Path)
    parser.add_argument("--strength", "-t", type=int, default=2)
    parser.add_argument("--python", action="store_true",
                        help="print a pytest.mark.parametrize decorator instead of JSON")
    parser.add_argument("--measure", type=Path, metavar="ROWS",
                        help="report the coverage of the rows in this JSON list instead")
    parser.add_argument("--show", type=int, default=20, help="missing combinations to list")
    args = parser.parse_args(argv)
    if args.strength < 1:
        parser.error("--strength must be 1 or more")
    try:
        model = Model(json.loads(args.model.read_text()))
        if args.measure:
            given = json.loads(args.measure.read_text())
            rows = [model.encode(row, f"row {n}") for n, row in enumerate(given, 1)]
            for n, row in enumerate(rows, 1):
                if len(row) != len(model.names):
                    raise ValueError(f"row {n}: does not give every parameter")
            rows = [[row[p] for p in range(len(model.names))] for row in rows]
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.measure:
        for n, row in enumerate(rows, 1):
            if model.violates(row):
                print(f"warning: row {n} matches a forbidden entry", file=sys.stderr)
        total, missing = measure(model, rows, args.strength)
        done = total - len(missing)
        print(f"{args.strength}-way: {done}/{total} feasible combinations covered "
              f"({100 * done / total if total else 100:.1f}%)")
        for combo in missing[:args.show]:
            print("  missing:", ", ".join(f"{model.names[p]}={model.values[p][v]!r}" for p, v in combo))
        return 0 if not missing else 1
    rows = [model.decode(row) for row in generate(model, args.strength)]
    if args.python:
        print(f'@pytest.mark.parametrize("{",".join(model.names)}", [')
        for row in rows:
            # json.dumps writes a valid Python string literal, in the double quotes the repo uses.
            cells = [json.dumps(v, ensure_ascii=False) if isinstance(v, str) else repr(v) for v in row.values()]
            print("    (" + ", ".join(cells) + ("," if len(row) == 1 else "") + "),")
        print("])")
    else:
        print(json.dumps(rows, indent=1))
    print(f"{len(rows)} rows, {args.strength}-way", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
