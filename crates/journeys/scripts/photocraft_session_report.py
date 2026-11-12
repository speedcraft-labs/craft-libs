#!/usr/bin/env python3
"""Summarize PhotoCraft session reports with session-cluster paired CIs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any


def percentile(values: list[float], p: float) -> float:
    xs = sorted(values)
    at = (len(xs) - 1) * p
    lo = math.floor(at)
    return xs[lo] + (xs[math.ceil(at)] - xs[lo]) * (at - lo)


def median_p95(values: list[int]) -> tuple[float, float]:
    return statistics.median(values) / 1e6, percentile([float(v) for v in values], 0.95) / 1e6


def value_list(sample: dict[str, Any], metric: str) -> list[int]:
    if metric == "stroke total":
        return [int(sample["duration_ns"])]
    if metric == "point" and sample["action"] == "brush":
        return [int(v) for v in sample.get("point_latencies_ns", [])]
    if metric == "step" and sample["action"] in {"move", "pan"}:
        return [int(v) for v in sample.get("step_latencies_ns", [])]
    if metric == "step" and sample["action"] == "zoom":
        return [int(sample["duration_ns"])]
    if metric == "action":
        return [int(sample["duration_ns"])]
    return []


def session_samples(session: dict[str, Any]) -> list[dict[str, Any]]:
    # Open is captured separately by the driver because it precedes the loaded-document actions.
    return [*session.get("samples", []), *session.get("open_samples", [])]


def metrics(samples: list[dict[str, Any]]) -> list[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for session in samples:
        for sample in session_samples(session):
            if sample["action"] == "brush":
                keys.update(((sample["label"] + " point", "point"), (sample["label"] + " stroke total", "stroke total")))
            elif sample["action"] in {"move", "pan", "zoom"}:
                keys.add((sample["label"] + " step", "step"))
            else:
                keys.add((sample["label"], "action"))
    return sorted(keys)


def samples_for(session: dict[str, Any], label: str, metric: str, phase: str) -> list[int]:
    result: list[int] = []
    for sample in session_samples(session):
        if sample.get("phase") != phase:
            continue
        if metric == "point":
            key = label.removesuffix(" point")
        elif metric == "stroke total":
            key = label.removesuffix(" stroke total")
        elif metric == "step":
            key = label.removesuffix(" step")
        else:
            key = label
        if sample.get("label") == key:
            result.extend(value_list(sample, metric))
    return result


def paired_ratio(sessions: list[dict[str, Any]], tier: str, left_role: str, right_role: str, label: str, metric: str, phase: str) -> tuple[float, list[float]]:
    by_pair: dict[int, dict[str, dict[str, Any]]] = {}
    for report in sessions:
        for session in report["sessions"]:
            if session["tier"] != tier:
                continue
            pair = int(session["pair"])
            role = session.get("side_role", session["side"])
            by_pair.setdefault(pair, {})[role] = session
    pair_logs = []
    for pair in sorted(by_pair):
        sides = by_pair[pair]
        if left_role not in sides or right_role not in sides:
            continue
        left = samples_for(sides[left_role], label, metric, phase)
        right = samples_for(sides[right_role], label, metric, phase)
        if not left or not right:
            continue
        pair_logs.append(math.log(statistics.median(left) / statistics.median(right)))
    if not pair_logs:
        raise ValueError(f"no paired values for {label} {phase}")
    return math.exp(statistics.median(pair_logs)), pair_logs


def ci_and_mde(pair_logs: list[float], seed: int = 315, draws: int = 10000) -> tuple[list[float], float, float]:
    rng = random.Random(seed)
    n = len(pair_logs)
    ratios = [math.exp(statistics.median(rng.choice(pair_logs) for _ in range(n))) for _ in range(draws)]
    ci = [percentile(ratios, 0.025), percentile(ratios, 0.975)]
    ratio = math.exp(statistics.median(pair_logs))
    half_width = ((ci[1] - ci[0]) / 2 / ratio) * 100
    mde = math.expm1((math.log(ci[1]) - math.log(ci[0])) / 2 * (1.959964 + 0.841621) / 1.959964) * 100
    return ci, half_width, mde


def load_reports(paths: list[Path]) -> list[dict[str, Any]]:
    reports = []
    for path in paths:
        report_path = path / "report.json" if path.is_dir() else path
        value = json.loads(report_path.read_text())
        if not value.get("session_complete"):
            raise ValueError(f"incomplete acquisition: {report_path}")
        if not value.get("gpu_process_checks_passed"):
            raise ValueError(f"GPU process check failed: {report_path}")
        reports.append(value)
    return reports


def rows_for(reports: list[dict[str, Any]], kind: str, aa_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    sessions = [session for report in reports for session in report["sessions"]]
    tier_names = sorted({session["tier"] for session in sessions})
    result = []
    calibration = {(r["tier"], r["label"], r["metric"], r["phase"]): r for r in (aa_rows or [])}
    for tier in tier_names:
        tier_sessions = [session for session in sessions if session["tier"] == tier]
        phases = ("cold", "warm")
        for label, metric in metrics(tier_sessions):
            for phase in phases:
                left_values = [v for session in tier_sessions for v in samples_for(session, label, metric, phase) if session.get("side_role") in {"a", "fork", "control"}]
                right_values = [v for session in tier_sessions for v in samples_for(session, label, metric, phase) if session.get("side_role") in {"b", "upstream", "slow"}]
                if not left_values or not right_values:
                    continue
                left_median, left_p95 = median_p95(left_values)
                right_median, right_p95 = median_p95(right_values)
                left_role, right_role = {
                    "aa": ("a", "b"),
                    "slowdown": ("control", "slow"),
                    "comparison": ("fork", "upstream"),
                }[kind]
                ratio, pair_logs = paired_ratio(reports, tier, left_role, right_role, label, metric, phase)
                if kind == "slowdown":
                    ratio = 1 / ratio
                    pair_logs = [-value for value in pair_logs]
                ci, half_width, current_mde = ci_and_mde(pair_logs, seed=315 + sum(map(ord, label + phase)))
                aa = calibration.get((tier, label, metric, phase))
                if kind == "aa":
                    mde = current_mde
                    gate_limit = 10.0 if label.startswith("open-") else 5.0
                    gate = "PASS" if len(pair_logs) >= 20 and ci[0] <= 1 <= ci[1] and half_width <= gate_limit else "FAIL"
                    verdict = gate
                elif kind == "slowdown":
                    mde = max(current_mde, aa["mde_pct"] * math.sqrt(20 / len(pair_logs))) if aa else current_mde
                    expected = statistics.mean(float(s.get("slow_delay_ms", 0)) for s in sessions if s.get("side_role") == "slow")
                    verdict = "A/A gate failed; descriptive only" if aa and aa["verdict"] != "PASS" else "slower detected" if ci[0] > 1 else "slowdown not resolved"
                else:
                    mde = max(current_mde, aa["mde_pct"] * math.sqrt(20 / len(pair_logs))) if aa else current_mde
                    verdict = (
                        "A/A gate failed; descriptive only"
                        if aa and aa["verdict"] != "PASS"
                        else "faster"
                        if ci[1] < 1
                        else "slower"
                        if ci[0] > 1
                        else "no measurable change"
                        if len(pair_logs) >= 10
                        else "insufficient paired sessions"
                    )
                result.append(
                    {
                        "tier": tier,
                        "label": label,
                        "metric": metric,
                        "phase": phase,
                        "pairs": len(pair_logs),
                        "left_role": left_role,
                        "right_role": right_role,
                        "left_median_ms": left_median,
                        "left_p95_ms": left_p95,
                        "right_median_ms": right_median,
                        "right_p95_ms": right_p95,
                        "ratio": ratio,
                        "ci95": ci,
                        "half_width_pct": half_width,
                        "mde_pct": mde,
                        "current_mde_pct": current_mde,
                        "aa_gate": aa["verdict"] if aa else None,
                        "expected_delay_ms": expected if kind == "slowdown" else None,
                        "verdict": verdict,
                    }
                )
    return result


def markdown(rows: list[dict[str, Any]], kind: str) -> str:
    ratio_name = {"aa": "A/B", "slowdown": "slow/control", "comparison": "fork/upstream"}[kind]
    lines = [
        f"Ratio is {ratio_name}; each ratio bootstraps paired session medians (10,000 resamples, seed derived from action). Pooled sample median/p95 are shown in ms. Cold is first use in that session; warm is subsequent repetitions.",
        "MDE is the approximate detectable percent change at two-sided alpha .05 and 80% power on log latency. For comparison/slowdown, the printed MDE is the larger of current-CI MDE and the A/A MDE scaled by sqrt(20 / paired count).",
        "",
        "| Tier | Action / metric | State | Left median/p95 ms | Right median/p95 ms | Ratio (95% CI) | Half-width % | MDE % | Verdict / A/A gate |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['tier']} | {row['label']} | {row['phase']} | {row['left_median_ms']:.2f}/{row['left_p95_ms']:.2f} | "
            f"{row['right_median_ms']:.2f}/{row['right_p95_ms']:.2f} | {row['ratio']:.3f} ({row['ci95'][0]:.3f}–{row['ci95'][1]:.3f}) | "
            f"{row['half_width_pct']:.2f} | {row['mde_pct']:.2f} | {row['verdict']}"
            + (f" / {row['aa_gate']}" if row["aa_gate"] else "")
            + " |"
        )
    if kind == "comparison":
        offenders = []
        for row in rows:
            if row["metric"] in {"point", "step"}:
                limit = 16.0
                if row["left_p95_ms"] >= limit:
                    offenders.append((row, row["left_role"], row["left_median_ms"], row["left_p95_ms"], limit))
                if row["right_p95_ms"] >= limit:
                    offenders.append((row, row["right_role"], row["right_median_ms"], row["right_p95_ms"], limit))
            if row["label"] in {"large-layer-visibility", "large-layer-blend-mode"}:
                limit = 100.0
                if row["left_median_ms"] >= limit or row["left_p95_ms"] >= limit:
                    offenders.append((row, row["left_role"], row["left_median_ms"], row["left_p95_ms"], limit))
                if row["right_median_ms"] >= limit or row["right_p95_ms"] >= limit:
                    offenders.append((row, row["right_role"], row["right_median_ms"], row["right_p95_ms"], limit))
        lines.extend(["", "Absolute bottlenecks against the requested user-facing marks:"])
        if not offenders:
            lines.append("None crossed the 16.00 ms interaction-step or 100 ms layer-toggle marks.")
        else:
            for row, role, median, p95, limit in offenders:
                lines.append(f"- {row['tier']} {row['label']} ({row['phase']}, {role}): median {median:.2f} ms, p95 {p95:.2f} ms; limit {limit:.2f} ms.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("aa", "slowdown", "comparison"))
    parser.add_argument("--reports", nargs="+", type=Path, required=True)
    parser.add_argument("--calibration", nargs="*", type=Path, default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reports = load_reports(args.reports)
    aa_rows = None
    if args.kind != "aa":
        if not args.calibration:
            raise ValueError("comparison and slowdown require the completed A/A report directories")
        aa_reports = load_reports(args.calibration)
        aa_rows = rows_for(aa_reports, "aa")
    rows = rows_for(reports, args.kind, aa_rows)
    thresholds = []
    if args.kind == "comparison":
        for row in rows:
            limit = 16.0 if row["metric"] in {"point", "step"} else 100.0 if row["label"] in {"large-layer-visibility", "large-layer-blend-mode"} else None
            if limit is None:
                continue
            for role, median, p95 in ((row["left_role"], row["left_median_ms"], row["left_p95_ms"]), (row["right_role"], row["right_median_ms"], row["right_p95_ms"])):
                if (row["metric"] in {"point", "step"} and p95 >= limit) or (limit == 100.0 and (median >= limit or p95 >= limit)):
                    thresholds.append({"tier": row["tier"], "label": row["label"], "phase": row["phase"], "side": role, "median_ms": median, "p95_ms": p95, "limit_ms": limit})
    result = {"kind": args.kind, "reports": [str(p) for p in args.reports], "rows": rows, "threshold_bottlenecks": thresholds, "markdown": markdown(rows, args.kind)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(result["markdown"], end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        raise SystemExit(f"PhotoCraft report failed: {error}")
