"""
Evaluation runner and benchmark comparison engine for Natural Language -> SQL.
Evaluates Approach A (Whole Schema) vs. Approach B (Table Selection) across 40+ test cases.
Measures execution accuracy, status classification accuracy, latency percentiles, and token efficiency.
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import statistics

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import config
from src.database import DatabaseConnection
from src.executor import QueryExecutor
from src.llm import LLMClient
from src.models import EvaluationResult, EvaluationTestCase, PipelineResult, QueryStatus
from src.pipeline import TextToSQLPipeline


def normalize_value(val: Any) -> Any:
    """Normalizes database values for robust equivalence checking."""
    if val is None:
        return None
    if isinstance(val, float):
        return round(val, 2)
    if isinstance(val, int):
        return val
    return str(val).strip()


def results_match(ground_truth_rows: List[Dict[str, Any]], generated_rows: List[Dict[str, Any]]) -> bool:
    """
    Compares two query result sets for semantic execution equivalence.
    Accounts for column alias differences and row ordering variations.
    """
    if len(ground_truth_rows) != len(generated_rows):
        return False

    if not ground_truth_rows and not generated_rows:
        return True

    # Convert each row to a tuple of sorted values (ignoring column alias differences)
    def row_to_tuple(row: Dict[str, Any]) -> Tuple[Any, ...]:
        return tuple(normalize_value(v) for v in row.values())

    gt_tuples = [row_to_tuple(r) for r in ground_truth_rows]
    gen_tuples = [row_to_tuple(r) for r in generated_rows]

    # First check: exact ordered match
    if gt_tuples == gen_tuples:
        return True

    # Second check: multiset / unordered equivalence (if query order wasn't strict)
    return sorted(gt_tuples, key=lambda t: str(t)) == sorted(gen_tuples, key=lambda t: str(t))


class BenchmarkRunner:
    """
    Orchestrates test case evaluation, ground truth verification, and metric aggregation.
    """

    def __init__(
        self,
        db_path: str = "store.db",
        eval_set_path: str = "eval_set.json",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.db_path = db_path
        self.eval_set_path = eval_set_path
        self.executor = QueryExecutor(db_path)
        self.llm_client = LLMClient(provider=provider, model=model)

    def load_test_cases(self) -> List[EvaluationTestCase]:
        """Loads evaluation test cases from JSON."""
        with open(self.eval_set_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [EvaluationTestCase(**item) for item in data]

    def execute_ground_truth(self, ground_truth_sql: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """Executes ground truth query to obtain expected result set."""
        if not ground_truth_sql:
            return None
        try:
            results, _ = self.executor.execute(ground_truth_sql)
            return results
        except Exception as e:
            sys.stderr.write(f"[WARN] Ground truth query failed to execute: {ground_truth_sql} | Error: {str(e)}\n")
            return None

    def evaluate_approach(self, approach_name: str, test_cases: List[EvaluationTestCase]) -> List[EvaluationResult]:
        """Runs evaluation over all test cases for a single approach."""
        pipeline = TextToSQLPipeline(
            db_path=self.db_path,
            llm_client=self.llm_client,
            approach=approach_name,
        )

        results: List[EvaluationResult] = []

        for tc in test_cases:
            # 1. Obtain ground truth results
            gt_results = self.execute_ground_truth(tc.ground_truth_sql)

            # 2. Run pipeline
            pipe_res = pipeline.run(tc.question, approach=approach_name)

            # 3. Check status match
            status_match = pipe_res.status == tc.expected_status

            # 4. Check execution match
            exec_match = False
            if tc.expected_status == QueryStatus.OK:
                if pipe_res.status == QueryStatus.OK and pipe_res.results is not None and gt_results is not None:
                    exec_match = results_match(gt_results, pipe_res.results)
            else:
                # For non-OK cases (AMBIGUOUS, UNANSWERABLE, REFUSED), execution match = status match
                exec_match = status_match

            results.append(
                EvaluationResult(
                    test_id=tc.id,
                    category=tc.category,
                    question=tc.question,
                    approach=approach_name,
                    expected_status=tc.expected_status,
                    actual_status=pipe_res.status,
                    status_match=status_match,
                    ground_truth_sql=tc.ground_truth_sql,
                    generated_sql=pipe_res.sql,
                    execution_match=exec_match,
                    error=pipe_res.note,
                    latency_ms=pipe_res.latency_ms,
                    prompt_tokens=pipe_res.prompt_tokens,
                    completion_tokens=pipe_res.completion_tokens,
                    retries_count=pipe_res.retries_count,
                )
            )

        return results

    def compute_metrics(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Calculates aggregate statistics and category breakdowns."""
        total = len(results)
        if total == 0:
            return {}

        exec_correct = sum(1 for r in results if r.execution_match)
        status_correct = sum(1 for r in results if r.status_match)

        latencies = [r.latency_ms for r in results]
        prompt_tokens = [r.prompt_tokens for r in results]
        completion_tokens = [r.completion_tokens for r in results]
        retries = sum(r.retries_count for r in results)

        # Category breakdown
        categories = sorted(list(set(r.category for r in results)))
        cat_metrics = {}
        for cat in categories:
            cat_res = [r for r in results if r.category == cat]
            cat_total = len(cat_res)
            cat_exec = sum(1 for r in cat_res if r.execution_match)
            cat_status = sum(1 for r in cat_res if r.status_match)
            cat_metrics[cat] = {
                "total": cat_total,
                "exec_accuracy": (cat_exec / cat_total) * 100.0 if cat_total > 0 else 0.0,
                "status_accuracy": (cat_status / cat_total) * 100.0 if cat_total > 0 else 0.0,
                "mean_latency_ms": statistics.mean([r.latency_ms for r in cat_res]),
            }

        # Security refusal rate (destructive + injection)
        sec_cases = [r for r in results if r.category in ("destructive", "injection")]
        sec_total = len(sec_cases)
        sec_refused = sum(1 for r in sec_cases if r.actual_status == QueryStatus.REFUSED)
        sec_accuracy = (sec_refused / sec_total) * 100.0 if sec_total > 0 else 100.0

        return {
            "total_queries": total,
            "overall_execution_accuracy": (exec_correct / total) * 100.0,
            "overall_status_accuracy": (status_correct / total) * 100.0,
            "security_refusal_accuracy": sec_accuracy,
            "mean_latency_ms": statistics.mean(latencies),
            "p50_latency_ms": statistics.median(latencies),
            "p90_latency_ms": statistics.quantiles(latencies, n=10)[8] if len(latencies) >= 10 else max(latencies),
            "avg_prompt_tokens": statistics.mean(prompt_tokens),
            "avg_completion_tokens": statistics.mean(completion_tokens),
            "total_retries": retries,
            "category_breakdown": cat_metrics,
        }


def format_markdown_report(metrics_a: Dict[str, Any], metrics_b: Dict[str, Any]) -> str:
    """Generates Markdown report comparing Approach A vs Approach B."""
    lines = [
        "# Empirical Benchmark Comparison: Approach A vs. Approach B",
        "",
        "| Metric | Approach A (Whole Schema) | Approach B (Table Selection) | Delta (B vs A) |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Overall Execution Accuracy** | **{metrics_a['overall_execution_accuracy']:.1f}%** | **{metrics_b['overall_execution_accuracy']:.1f}%** | {metrics_b['overall_execution_accuracy'] - metrics_a['overall_execution_accuracy']:+.1f}% |",
        f"| **Status Classification Accuracy** | {metrics_a['overall_status_accuracy']:.1f}% | {metrics_b['overall_status_accuracy']:.1f}% | {metrics_b['overall_status_accuracy'] - metrics_a['overall_status_accuracy']:+.1f}% |",
        f"| **Security Refusal Accuracy** | **{metrics_a['security_refusal_accuracy']:.1f}%** | **{metrics_b['security_refusal_accuracy']:.1f}%** | 0.0% |",
        f"| **Mean Latency** | {metrics_a['mean_latency_ms']:.2f} ms | {metrics_b['mean_latency_ms']:.2f} ms | {metrics_b['mean_latency_ms'] - metrics_a['mean_latency_ms']:+.2f} ms |",
        f"| **p50 Latency** | {metrics_a['p50_latency_ms']:.2f} ms | {metrics_b['p50_latency_ms']:.2f} ms | {metrics_b['p50_latency_ms'] - metrics_a['p50_latency_ms']:+.2f} ms |",
        f"| **p90 Latency** | {metrics_a['p90_latency_ms']:.2f} ms | {metrics_b['p90_latency_ms']:.2f} ms | {metrics_b['p90_latency_ms'] - metrics_a['p90_latency_ms']:+.2f} ms |",
        f"| **Avg Prompt Tokens** | {metrics_a['avg_prompt_tokens']:.1f} | {metrics_b['avg_prompt_tokens']:.1f} | {metrics_b['avg_prompt_tokens'] - metrics_a['avg_prompt_tokens']:+.1f} |",
        f"| **Avg Completion Tokens** | {metrics_a['avg_completion_tokens']:.1f} | {metrics_b['avg_completion_tokens']:.1f} | {metrics_b['avg_completion_tokens'] - metrics_a['avg_completion_tokens']:+.1f} |",
        f"| **Total Self-Correction Retries** | {metrics_a['total_retries']} | {metrics_b['total_retries']} | {metrics_b['total_retries'] - metrics_a['total_retries']:+d} |",
        "",
        "## Accuracy Breakdown by Query Category",
        "",
        "| Category | Test Count | Approach A Accuracy | Approach B Accuracy |",
        "| :--- | :---: | :---: | :---: |",
    ]

    all_cats = sorted(list(metrics_a["category_breakdown"].keys()))
    for cat in all_cats:
        ca = metrics_a["category_breakdown"][cat]
        cb = metrics_b["category_breakdown"][cat]
        lines.append(f"| `{cat}` | {ca['total']} | {ca['exec_accuracy']:.1f}% | {cb['exec_accuracy']:.1f}% |")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate and benchmark Text-to-SQL approaches.")
    parser.add_argument("--db", type=str, default="store.db", help="Path to SQLite database")
    parser.add_argument("--eval-set", type=str, default="eval_set.json", help="Path to eval_set.json")
    parser.add_argument("--output", type=str, default="eval_results.json", help="Path to export JSON results")
    parser.add_argument("--provider", type=str, default=None, help="LLM provider")
    parser.add_argument("--model", type=str, default=None, help="LLM model")

    args = parser.parse_args()

    sys.stderr.write(f"[*] Initializing evaluation runner on '{args.db}' with '{args.eval_set}'...\n")
    runner = BenchmarkRunner(
        db_path=args.db,
        eval_set_path=args.eval_set,
        provider=args.provider,
        model=args.model,
    )

    test_cases = runner.load_test_cases()
    sys.stderr.write(f"[*] Loaded {len(test_cases)} evaluation test cases.\n")

    # Run Approach A
    sys.stderr.write("[*] Benchmarking Approach A (Whole Schema)...\n")
    results_a = runner.evaluate_approach("whole_schema", test_cases)
    metrics_a = runner.compute_metrics(results_a)

    # Run Approach B
    sys.stderr.write("[*] Benchmarking Approach B (Table Selection)...\n")
    results_b = runner.evaluate_approach("table_selection", test_cases)
    metrics_b = runner.compute_metrics(results_b)

    # Generate Markdown comparison
    report_md = format_markdown_report(metrics_a, metrics_b)
    print("\n" + report_md + "\n")

    # Save structured results
    export_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_test_cases": len(test_cases),
        "metrics": {
            "approach_a_whole_schema": metrics_a,
            "approach_b_table_selection": metrics_b,
        },
        "results_approach_a": [r.model_dump() for r in results_a],
        "results_approach_b": [r.model_dump() for r in results_b],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2)

    sys.stderr.write(f"[+] Evaluation completed successfully. Exported full results to '{args.output}'.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
