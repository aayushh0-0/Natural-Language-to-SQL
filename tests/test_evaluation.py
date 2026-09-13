"""
Unit tests for evaluation harness, semantic execution matching, and metric calculations.
"""

import pytest

from evaluate import BenchmarkRunner, normalize_value, results_match
from src.models import EvaluationTestCase, QueryStatus


class TestSemanticEquivalenceMatcher:
    """Tests for results_match and normalize_value comparison logic."""

    def test_normalize_value_types(self):
        assert normalize_value(None) is None
        assert normalize_value(12.3456) == 12.35
        assert normalize_value(42) == 42
        assert normalize_value("  hello world  ") == "hello world"

    def test_results_match_exact(self):
        gt = [{"id": 1, "name": "AC/DC"}, {"id": 2, "name": "Accept"}]
        gen = [{"id": 1, "name": "AC/DC"}, {"id": 2, "name": "Accept"}]
        assert results_match(gt, gen) is True

    def test_results_match_different_column_names(self):
        # Column aliases should not affect semantic equivalence
        gt = [{"ArtistId": 1, "ArtistName": "AC/DC"}]
        gen = [{"id": 1, "name": "AC/DC"}]
        assert results_match(gt, gen) is True

    def test_results_match_unordered_multiset(self):
        gt = [{"id": 1, "val": 10.0}, {"id": 2, "val": 20.0}]
        gen = [{"id": 2, "val": 20.0}, {"id": 1, "val": 10.0}]
        assert results_match(gt, gen) is True

    def test_results_match_float_rounding(self):
        gt = [{"total": 15.991}]
        gen = [{"total": 15.994}]
        assert results_match(gt, gen) is True

    def test_results_mismatch_length(self):
        gt = [{"id": 1}]
        gen = [{"id": 1}, {"id": 2}]
        assert results_match(gt, gen) is False

    def test_results_mismatch_values(self):
        gt = [{"id": 1, "name": "AC/DC"}]
        gen = [{"id": 1, "name": "Metallica"}]
        assert results_match(gt, gen) is False

    def test_results_match_empty(self):
        assert results_match([], []) is True


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner test case loading and execution."""

    def test_load_test_cases(self):
        runner = BenchmarkRunner(db_path="store.db", eval_set_path="eval_set.json")
        test_cases = runner.load_test_cases()
        assert len(test_cases) >= 40
        assert all(isinstance(tc, EvaluationTestCase) for tc in test_cases)

    def test_execute_ground_truth(self):
        runner = BenchmarkRunner(db_path="store.db", eval_set_path="eval_set.json")
        res = runner.execute_ground_truth("SELECT 1 AS num;")
        assert res == [{"num": 1}]
        assert runner.execute_ground_truth(None) is None

    def test_compute_metrics(self):
        runner = BenchmarkRunner(db_path="store.db", eval_set_path="eval_set.json")
        cases = runner.load_test_cases()[:5]
        results = runner.evaluate_approach("whole_schema", cases)
        metrics = runner.compute_metrics(results)
        assert "overall_execution_accuracy" in metrics
        assert "overall_status_accuracy" in metrics
        assert "mean_latency_ms" in metrics
        assert "avg_prompt_tokens" in metrics
