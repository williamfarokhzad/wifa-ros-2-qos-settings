"""Offline ROS 2 topic QoS audit for two explicit policies and one late join."""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path


RELIABILITY = ("best_effort", "reliable")
DURABILITY = ("volatile", "transient_local")


@dataclass(frozen=True)
class Profile:
    reliability: str
    durability: str

    def __post_init__(self):
        if self.reliability not in RELIABILITY:
            raise ValueError("reliability must be best_effort or reliable")
        if self.durability not in DURABILITY:
            raise ValueError("durability must be volatile or transient_local")


def mismatches(offered, requested):
    """Return unmet requests in a stable order. The direction matters."""
    return [
        policy for policy, levels in (("reliability", RELIABILITY), ("durability", DURABILITY))
        if levels.index(getattr(offered, policy)) < levels.index(getattr(requested, policy))
    ]


def require_keys(obj, keys, label):
    if not isinstance(obj, dict) or obj.keys() != set(keys):
        raise ValueError(f"{label} must contain exactly: {', '.join(keys)}")


def audit(case):
    require_keys(case, ("publisher", "subscriber", "before_join", "after_join"), "scenario")
    publisher, subscriber = case["publisher"], case["subscriber"]
    require_keys(publisher, ("reliability", "durability", "depth"), "publisher")
    require_keys(subscriber, ("reliability", "durability"), "subscriber")
    depth = publisher["depth"]
    if type(depth) is not int or depth < 1:
        raise ValueError("publisher depth must be a positive integer (keep last)")
    before, after = case["before_join"], case["after_join"]
    if any(not isinstance(group, list) for group in (before, after)):
        raise ValueError("before_join and after_join must be arrays")
    sequence = before + after
    if any(type(n) is not int or n < 1 for n in sequence):
        raise ValueError("sample IDs must be positive integers")
    if any(a >= b for a, b in zip(sequence, sequence[1:])):
        raise ValueError("sample IDs must be strictly increasing across the join")
    offered = Profile(publisher["reliability"], publisher["durability"])
    requested = Profile(**subscriber)
    reasons = mismatches(offered, requested)
    # This history is an idealized publisher cache, not a DDS resource prediction.
    replay = before[-depth:] if not reasons and requested.durability == "transient_local" else []
    return {
        "compatible_for_modeled_policies": not reasons,
        "unmet_requests": reasons,
        "modeled_replay_ids": replay,
        "eligible_live_ids": after if not reasons else [],
    }


def unique_fields(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate field: {key}")
        obj[key] = value
    return obj


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="path to a scenario JSON file")
    args = parser.parse_args(argv)
    try:
        case = json.loads(args.scenario.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
        result = audit(case)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Invalid scenario: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
