import unittest

from timing_utils import normalize_incident_timing_metadata


class IncidentTimingMetadataTests(unittest.TestCase):
    def test_normal_incident_timing(self):
        metadata = normalize_incident_timing_metadata(
            event_elapsed_ms=42000,
            clip_start_elapsed_ms=32000,
            clip_end_elapsed_ms=47000,
        )
        self.assertEqual(metadata["event_elapsed_ms"], 42000)
        self.assertEqual(metadata["clip_start_elapsed_ms"], 32000)
        self.assertEqual(metadata["clip_end_elapsed_ms"], 47000)
        self.assertEqual(metadata["video_offset_ms"], 10000)
        self.assertLessEqual(metadata["clip_start_elapsed_ms"], metadata["event_elapsed_ms"])
        self.assertLessEqual(metadata["event_elapsed_ms"], metadata["clip_end_elapsed_ms"])

    def test_early_violation_clamps_start_to_zero(self):
        metadata = normalize_incident_timing_metadata(
            event_elapsed_ms=3000,
            clip_start_elapsed_ms=-7000,
            clip_end_elapsed_ms=8000,
        )
        self.assertEqual(metadata["clip_start_elapsed_ms"], 0)
        self.assertEqual(metadata["video_offset_ms"], 3000)

    def test_invalid_order_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_incident_timing_metadata(
                event_elapsed_ms=42000,
                clip_start_elapsed_ms=50000,
                clip_end_elapsed_ms=47000,
            )


if __name__ == "__main__":
    unittest.main()
