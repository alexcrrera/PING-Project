"""Camera adapter lifecycle and cached-frame behavior without camera hardware."""

from io import BytesIO
import queue
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from PIL import Image

from ping_base.camera import OpenCVCameraSource, SimulatedCameraSource, _LatestFrameSource


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("Camera worker did not reach the expected state")


class CameraTests(unittest.TestCase):
    @staticmethod
    def motion(**values):
        return SimpleNamespace(x_m=values.get("x_m", 0), y_m=values.get("y_m", 0),
                               heading_deg=values.get("heading_deg", 0),
                               pitch_deg=0, roll_deg=0)

    def test_bound_camera_is_still_at_idle_and_retraces_a_reversed_drive(self):
        source = SimulatedCameraSource(width=320, height=180)
        source.set_motion(self.motion())
        origin = source.render(0).tobytes()
        self.assertEqual(origin, source.render(30).tobytes())
        source.set_motion(self.motion(y_m=7))
        self.assertNotEqual(origin, source.render(30).tobytes())
        source.set_motion(self.motion())
        self.assertEqual(origin, source.render(60).tobytes())

    def test_camera_turns_through_a_fixed_world_and_copies_input_pose(self):
        source = SimulatedCameraSource(width=320, height=180)
        motion = self.motion()
        source.set_motion(motion)
        forward = source.render(0).tobytes()
        motion.heading_deg = 90
        # Mutable callers cannot race with the capture worker after set_motion.
        self.assertEqual(forward, source.render(0).tobytes())
        source.set_motion(motion)
        self.assertNotEqual(forward, source.render(0).tobytes())
        source.set_motion(self.motion(heading_deg=360))
        self.assertEqual(forward, source.render(0).tobytes())

    def test_virtual_world_cache_is_bounded_and_reproducible_after_eviction(self):
        source = SimulatedCameraSource(width=320, height=180)
        first = source._terrain_chunk(0, 0)
        for index in range(110):
            source._terrain_chunk(index, 10)
        self.assertLessEqual(len(source._terrain_cache), 100)
        self.assertEqual(first, source._terrain_chunk(0, 0))

    def test_camera_rejects_nonfinite_pose_before_publishing_it(self):
        source = SimulatedCameraSource(width=320, height=180)
        with self.assertRaises(ValueError):
            source.set_motion(self.motion(x_m=float("nan")))

    def test_simulation_publishes_real_jpegs_and_stops_without_leaking_worker(self):
        source = SimulatedCameraSource(width=320, height=180, fps=30)
        try:
            source.start()
            worker = source._thread
            source.start()
            self.assertIs(source._thread, worker)
            wait_until(lambda: source.latest_frame() is not None)
            first = source.latest_frame()
            with Image.open(BytesIO(first.jpeg)) as image:
                self.assertEqual(image.size, (320, 180))
                self.assertEqual(image.format, "JPEG")
            wait_until(lambda: source.latest_frame().sequence > first.sequence)
            self.assertEqual(source.status, "Simulation")
            self.assertIsNone(source.error)
        finally:
            source.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(source.status, "Stopped")
        source.close()  # Shutdown hooks may run more than once.

    def test_capture_failure_reports_error_and_releases_adapter(self):
        released = threading.Event()

        class BrokenCamera(_LatestFrameSource):
            name = "broken-test"
            simulated = False

            def _capture_frame(self, now):
                raise RuntimeError("Capture disconnected")

            def _close(self):
                released.set()

        source = BrokenCamera(width=320, height=180, fps=12)
        try:
            source.start()
            self.assertTrue(released.wait(1))
            self.assertEqual(source.status, "Unavailable")
            self.assertEqual(source.error, "Capture disconnected")
            self.assertIsNone(source.latest_frame())
        finally:
            source.close()

    def test_usb_timeout_is_finite_and_stalled_capture_is_terminated(self):
        source = OpenCVCameraSource(timeout=.01)
        source._messages = queue.Queue()
        source._last_received = time.monotonic() - 1
        process = Mock()
        process.is_alive.side_effect = [True, True, False]
        source._process = process
        with self.assertRaisesRegex(RuntimeError, "No camera frame"):
            source._capture_frame(time.monotonic())
        # No child process or device is opened: emulate a stalled driver's
        # process to verify the bounded fallback during application shutdown.
        source._messages = Mock()
        source._capture_stop = Mock()
        source.close()
        source._capture_stop.set.assert_called_once()
        process.terminate.assert_called_once()
        self.assertEqual(process.join.call_count, 2)
        process.close.assert_called_once()

    def test_invalid_rate_or_timeout_is_rejected_before_opening_hardware(self):
        for fps in (0, -1, float("nan"), 61):
            with self.assertRaises(ValueError):
                SimulatedCameraSource(fps=fps)
        with self.assertRaises(ValueError):
            OpenCVCameraSource(timeout=float("inf"))


if __name__ == "__main__":
    unittest.main()
