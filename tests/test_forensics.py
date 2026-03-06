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


if __name__ == "__main__":
    unittest.main()
