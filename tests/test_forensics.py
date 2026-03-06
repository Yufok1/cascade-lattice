import unittest

import pandas as pd

from cascade.forensics import DataForensics


class ForensicsModeTests(unittest.TestCase):
    def test_auto_mode_uses_anomaly_for_single_failure_payload(self):
        df = pd.DataFrame([{
            "component": "debug_runtime",
            "tool": "forensics_analyze",
            "status": 404,
            "trace_id": "trace-123",
            "retry_count": 2,
            "timestamp": "2026-03-06T03:40:15Z",
            "context": {"route": "caller", "source": "agent-inner"},
            "error": "HTTP Error 404: Not Found",
        }])

        report = DataForensics().analyze(df, mode="auto")

        ops = {artifact.inferred_operation for artifact in report.artifacts}
        self.assertEqual(report.analysis_mode, "anomaly")
        self.assertIn("TRACE_CORRELATION", ops)
        self.assertIn("DEBUG_ERROR_SIGNAL", ops)
        self.assertTrue(report.ghost_log.operations)
        self.assertEqual(report.summary()["analysis_mode"], "anomaly")

    def test_auto_mode_uses_anomaly_for_small_structured_failure_burst(self):
        rows = []
        for i in range(6):
            rows.append({
                "component": "gateway_mux",
                "event_type": "http_failure",
                "timestamp": f"2026-03-06T03:59:0{i}Z",
                "tool": "invoke_slot",
                "route": "/api/tool/invoke_slot",
                "status": "error",
                "trace_id": f"trace_eval_pkg_{10+i}",
                "session_id": f"sess_eval_pkg_{'abc'[i // 2]}",
                "http": {
                    "status_code": 500 if i < 4 else 429,
                    "method": "POST",
                    "path": "/api/tool/invoke_slot",
                },
                "python": {
                    "exception_type": "RuntimeError" if i < 4 else "TimeoutError",
                    "module": "server.mcp_proxy",
                    "stack_hint": "Traceback (most recent call last): server.py line 4632 in proxy_call",
                },
                "context": {
                    "mode": "live_validation",
                    "source": "mcp_direct",
                },
            })

        report = DataForensics().analyze(pd.DataFrame(rows), mode="auto")

        ops = {artifact.inferred_operation for artifact in report.artifacts}
        self.assertEqual(report.analysis_mode, "anomaly")
        self.assertIn("DEBUG_ERROR_SIGNAL", ops)
        self.assertIn("NESTED_FAILURE_CONTEXT", ops)
        self.assertIn("OBSERVABILITY_ROUTE", ops)

    def test_auto_mode_keeps_small_tabular_data_in_dataset_mode(self):
        df = pd.DataFrame({
            "created_at": pd.date_range("2026-03-06", periods=6, freq="h"),
            "value": [10, 11, 12, 13, 14, 15],
            "worker": ["a", "b", "a", "b", "a", "b"],
        })

        report = DataForensics().analyze(df, mode="auto")

        self.assertEqual(report.analysis_mode, "dataset")

    def test_dataset_mode_preserves_multirow_artifacts(self):
        df = pd.DataFrame({
            "created_at": pd.date_range("2026-03-06", periods=12, freq="h"),
            "request_id": [f"req-{i:03d}" for i in range(12)],
        })

        report = DataForensics().analyze(df, mode="dataset")

        ops = {artifact.inferred_operation for artifact in report.artifacts}
        self.assertEqual(report.analysis_mode, "dataset")
        self.assertTrue(any(op.startswith("BATCH") or op.startswith("SCHEDULED_JOB") for op in ops))

    def test_dataset_mode_single_row_does_not_force_anomaly_artifacts(self):
        df = pd.DataFrame([{
            "component": "debug_runtime",
            "tool": "forensics_analyze",
            "status": 404,
            "error": "HTTP Error 404: Not Found",
        }])

        report = DataForensics().analyze(df, mode="dataset")

        ops = {artifact.inferred_operation for artifact in report.artifacts}
        self.assertEqual(report.analysis_mode, "dataset")
        self.assertNotIn("DEBUG_ERROR_SIGNAL", ops)
        self.assertNotIn("TRACE_CORRELATION", ops)

    def test_truncation_artifact_uses_actual_column_name(self):
        df = pd.DataFrame({
            "route": ["/api/tool/invoke_slot"] * 6,
        })

        report = DataForensics().analyze(df, mode="dataset")

        trunc = [a for a in report.artifacts if a.inferred_operation.startswith("FIELD_LENGTH_LIMIT_")]
        self.assertTrue(trunc)
        self.assertEqual(trunc[0].column, "route")


if __name__ == "__main__":
    unittest.main()
