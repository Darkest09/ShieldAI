"""Evaluate PII-detection effectiveness against the labelled synthetic dataset.

Produces the metrics the proposal's RQ1/RQ2 require: detection accuracy
(precision / recall / F1), privacy-leakage rate and leakage-reduction, false
positive/negative rates, per-entity breakdown, per-prompt latency, and resource
consumption (CPU time + peak traced memory). Outputs JSON + a markdown report.

Usage:
    python scripts/generate_synthetic_dataset.py --n 300
    python scripts/evaluate.py --data data/eval/synthetic_banking.jsonl

Requires the project deps installed (Presidio + spaCy model).
"""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path

from app.core.presidio_setup import build_analyzer_engine
from app.proxy.config_store import DEFAULT_CONFIG


def _overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def evaluate(data_path: str, engine_kind: str | None = None) -> dict:
    if engine_kind:
        from app.core.settings import settings as _s
        _s.nlp_engine = engine_kind
    engine = build_analyzer_engine(DEFAULT_CONFIG)
    records = [json.loads(line) for line in Path(data_path).read_text(encoding="utf-8").splitlines() if line.strip()]

    tp = fp = fn = 0
    per_entity = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    latencies: list[float] = []
    # Span-level privacy metrics (does the gateway redact the sensitive span at all?)
    gold_spans_total = 0
    gold_spans_covered = 0      # overlapped by ANY detection -> would be scrubbed
    fp_spurious = 0             # detection overlapping no gold span (true noise)
    fp_type_overlap = 0         # detection overlapping a gold span, different label (safe over-scrub)

    tracemalloc.start()
    cpu_t0 = time.process_time()
    for rec in records:
        text = rec["text"]
        gold = rec["entities"]

        t0 = time.perf_counter()
        results = engine.analyze(text=text, language="en")
        latencies.append((time.perf_counter() - t0) * 1000.0)

        detected = [{"start": r.start, "end": r.end, "type": str(r.entity_type)} for r in results]
        gold_matched = [False] * len(gold)
        det_matched = [False] * len(detected)

        for gi, g in enumerate(gold):
            for di, d in enumerate(detected):
                if det_matched[di]:
                    continue
                # Same entity type (or any overlap for PERSON/LOCATION fuzz) + span overlap
                if _overlap(g["start"], g["end"], d["start"], d["end"]):
                    same = d["type"] == g["type"]
                    if same:
                        gold_matched[gi] = True
                        det_matched[di] = True
                        tp += 1
                        per_entity[g["type"]]["tp"] += 1
                        break

        # Span-level privacy coverage: was each gold span overlapped by ANY detection?
        for g in gold:
            gold_spans_total += 1
            if any(_overlap(g["start"], g["end"], d["start"], d["end"]) for d in detected):
                gold_spans_covered += 1

        for gi, g in enumerate(gold):
            if not gold_matched[gi]:
                fn += 1
                per_entity[g["type"]]["fn"] += 1
        for di, d in enumerate(detected):
            if not det_matched[di]:
                fp += 1
                per_entity[d["type"]]["fp"] += 1
                if any(_overlap(d["start"], d["end"], g["start"], g["end"]) for g in gold):
                    fp_type_overlap += 1  # redacts a real PII span under a different label
                else:
                    fp_spurious += 1

    cpu_seconds = time.process_time() - cpu_t0
    _, peak_memory_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    def prf(tp, fp, fn):
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        return round(prec, 4), round(rec, 4), round(f1, 4)

    prec, rec, f1 = prf(tp, fp, fn)
    latencies.sort()
    n = len(latencies) or 1
    privacy_coverage = round(gold_spans_covered / gold_spans_total, 4) if gold_spans_total else 0.0
    privacy_leakage_rate = round(1 - privacy_coverage, 4)
    return {
        "dataset": data_path,
        "records": len(records),
        "privacy": {
            "span_coverage": privacy_coverage,
            "spans_covered": gold_spans_covered,
            "spans_total": gold_spans_total,
            "privacy_leakage_rate": privacy_leakage_rate,
            "leakage_reduction_pct": round(privacy_coverage * 100, 2),
            "note": "span_coverage = fraction of sensitive spans redacted by ANY detector. "
                    "privacy_leakage_rate = 1 - span_coverage (the fraction that would still "
                    "reach an external LLM). leakage_reduction_pct compares against a "
                    "no-gateway baseline that leaks 100% of spans.",
        },
        "false_positive_breakdown": {
            "spurious": fp_spurious,
            "type_overlap_safe": fp_type_overlap,
            "note": "type_overlap_safe = a real PII span flagged under a different label "
                    "(still redacted); spurious = noise on non-sensitive text.",
        },
        "overall": {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": prec, "recall": rec, "f1": f1,
            "false_negative_rate": round(fn / (tp + fn), 4) if (tp + fn) else 0.0,
            "false_positive_rate": round(fp / (tp + fp), 4) if (tp + fp) else 0.0,
        },
        "latency_ms": {
            "mean": round(sum(latencies) / n, 2),
            "p50": round(latencies[int(0.50 * (n - 1))], 2),
            "p95": round(latencies[int(0.95 * (n - 1))], 2),
        },
        "resources": {
            "cpu_seconds": round(cpu_seconds, 3),
            "peak_memory_bytes": peak_memory_bytes,
            "peak_memory_mb": round(peak_memory_bytes / (1024 * 1024), 2),
            "note": "CPU time is process_time() across the analyze loop; peak memory is "
                    "tracemalloc tracked Python allocations (cross-platform proxy, not full RSS).",
        },
        "per_entity": {
            et: {**v, "precision": prf(v["tp"], v["fp"], v["fn"])[0],
                 "recall": prf(v["tp"], v["fp"], v["fn"])[1]}
            for et, v in sorted(per_entity.items())
        },
    }


def to_markdown(report: dict) -> str:
    o = report["overall"]
    p = report["privacy"]
    fpb = report["false_positive_breakdown"]
    r = report["resources"]
    lines = [
        "# ShieldAI / PPAG — PII Detection Evaluation",
        "",
        f"- Dataset: `{report['dataset']}` ({report['records']} prompts)",
        f"- **Privacy span coverage (redacted / total): {p['span_coverage']:.2%}** "
        f"({p['spans_covered']}/{p['spans_total']}) — the gateway-relevant metric",
        f"- **Privacy leakage rate: {p['privacy_leakage_rate']:.2%}** "
        f"(leakage reduction vs no-gateway baseline: {p['leakage_reduction_pct']:.2f}%)",
        f"- Strict per-type: Precision {o['precision']:.2%} · Recall {o['recall']:.2%} · F1 {o['f1']:.2%}",
        f"- False positives: {fpb['spurious']} spurious · {fpb['type_overlap_safe']} safe over-scrub "
        "(real PII under a different label)",
        f"- False-negative rate: {o['false_negative_rate']:.2%}",
        f"- Latency (ms): mean {report['latency_ms']['mean']}, "
        f"p50 {report['latency_ms']['p50']}, p95 {report['latency_ms']['p95']}",
        f"- Resources: {r['cpu_seconds']:.3f}s CPU · {r['peak_memory_mb']} MB peak traced memory",
        "",
        "## Per-entity",
        "",
        "| Entity | TP | FP | FN | Precision | Recall |",
        "|---|---|---|---|---|---|",
    ]
    for et, v in report["per_entity"].items():
        lines.append(
            f"| {et} | {v['tp']} | {v['fp']} | {v['fn']} | "
            f"{v['precision']:.2%} | {v['recall']:.2%} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/eval/synthetic_banking.jsonl")
    ap.add_argument("--out-json", default="data/eval/report.json")
    ap.add_argument("--out-md", default="data/eval/report.md")
    ap.add_argument("--engine", choices=["spacy", "transformers"], default=None,
                    help="Override the NER backend for this run.")
    args = ap.parse_args()

    report = evaluate(args.data, engine_kind=args.engine)
    report["engine"] = args.engine or "default"
    Path(args.out_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    Path(args.out_md).write_text(to_markdown(report), encoding="utf-8")
    o = report["overall"]
    p = report["privacy"]
    print(
        f"Precision {o['precision']:.2%} | Recall {o['recall']:.2%} | F1 {o['f1']:.2%} "
        f"| Leakage {p['privacy_leakage_rate']:.2%}"
    )
    print(f"Reports written to {args.out_json} and {args.out_md}")


if __name__ == "__main__":
    main()
