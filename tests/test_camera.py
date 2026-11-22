"""Camera adapter lifecycle and cached-frame behavior without camera hardware."""

from io import BytesIO
import queue
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from ping_base.camera import FFmpegCameraSource, OpenCVCameraSource, SimulatedCameraSource, _LatestFrameSource, _opencv_capture_loop
from ping_base.gimbal import GimbalPose, StabilizationMode, VirtualGimbal


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("Camera worker did not reach the expected state")


class CameraTests(unittest.TestCase):
    def test_ffmpeg_source_reads_framed_jpeg(self):
        output = BytesIO()
        Image.new("RGB", (64, 48), "red").save(output, "JPEG")
        jpeg = output.getvalue()
        source = FFmpegCameraSource("tcp://example:8888")
        source._process = SimpleNamespace(stdout=BytesIO(jpeg + jpeg))
        first = source._capture_frame(0)
        second = source._capture_frame(0)
        self.assertEqual(first[:3], (jpeg, 64, 48))
        self.assertEqual(second[:3], (jpeg, 64, 48))

    def test_ffmpeg_reconnects_and_clears_error_after_new_frame(self):
        source = FFmpegCameraSource("tcp://example:8888")
        def capture(now):
            if not source._open.called:
                raise RuntimeError("stream ended")
            source._stop.set()
            return b"jpeg", 64, 48, now
        source._capture_frame = Mock(side_effect=capture)
        source._open = Mock()
        source._close = Mock()
        with patch.object(source._stop, "wait", return_value=False):
            source._run()
        source._open.assert_called_once()
        self.assertEqual(source.status, "Connected")
        self.assertIsNone(source.error)
        self.assertEqual(source.latest_frame().jpeg, b"jpeg")

    def test_network_source_uses_newest_queued_frame(self):
        source = OpenCVCameraSource("tcp://example:8888")
        source._messages = queue.Queue()
        source._messages.put(("frame", b"old", 1, 1, 1.0))
        source._messages.put(("frame", b"new", 2, 2, 2.0))
        self.assertEqual(source._capture_frame(3.0), (b"new", 2, 2, 2.0))

    def test_network_capture_drains_frames_without_sleeping_at_display_rate(self):
        capture = Mock()
        capture.read.return_value = (True, SimpleNamespace(shape=(720, 1280, 3)))
        encoded = Mock()
        encoded.tobytes.return_value = b"jpeg"
        cv = SimpleNamespace(
            VideoCapture=Mock(return_value=capture), CAP_FFMPEG=1900,
            CAP_PROP_OPEN_TIMEOUT_MSEC=53, CAP_PROP_READ_TIMEOUT_MSEC=54,
            CAP_PROP_BUFFERSIZE=38, IMWRITE_JPEG_QUALITY=1,
            imencode=Mock(return_value=(True, encoded)),
        )
        stop = Mock()
        stop.is_set.side_effect = [False] * 6 + [True]
        messages = queue.Queue(maxsize=2)
        with patch.dict("sys.modules", {"cv2": cv}), patch.dict("os.environ", {}), patch(
                "ping_base.camera.time.monotonic", side_effect=[0, .01, .02, .03, .10, .11]):
            _opencv_capture_loop("tcp://192.168.68.56:8888", 960, 540, 12, messages, stop)
        self.assertEqual(capture.read.call_count, 6)
        self.assertEqual(cv.imencode.call_count, 2)
        stop.wait.assert_not_called()
        capture.release.assert_called_once()
        cv.VideoCapture.assert_called_once_with("tcp://192.168.68.56:8888", 1900, [53, 20000, 54, 3000])
        self.assertEqual(messages.get_nowait()[2:4], (1280, 720))

    @staticmethod
    def motion(**values):
        return SimpleNamespace(x_m=values.get("x_m", 0), y_m=values.get("y_m", 0),
                               heading_deg=values.get("heading_deg", 0),
                               pitch_deg=values.get("pitch_deg", 0), roll_deg=values.get("roll_deg", 0))

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

    def test_gimbal_pan_matches_rover_heading_without_moving_the_rover(self):
        source = SimulatedCameraSource(width=320, height=180)
        source.set_motion(self.motion())
        # The fixed chassis is the only fixture that follows the rover's body.
        with unittest.mock.patch.object(source, "_draw_fenders"):
            source.set_motion(self.motion())
            source.set_gimbal(GimbalPose(yaw_deg=90))
            panned = source.render(0).tobytes()
            source.set_motion(self.motion(heading_deg=90))
            source.set_gimbal(GimbalPose())
            self.assertEqual(panned, source.render(0).tobytes())

    def test_gimbal_tilt_changes_view_and_home_restores_identical_frame(self):
        source = SimulatedCameraSource(width=320, height=180)
        source.set_motion(self.motion())
        home = source.render(0).tobytes()
        frames = {}
        for yaw in (-90, 0, 90):
            for pitch in (-60, -20, 20, 60):
                source.set_gimbal(GimbalPose(yaw, pitch))
                frame = source.render(0)
                self.assertEqual(frame.size, (320, 180))
                self.assertNotEqual(home, frame.tobytes())
                frames[yaw, pitch] = frame.tobytes()
        self.assertNotEqual(frames[0, 20], frames[0, -20])
        self.assertNotEqual(frames[-90, -20], frames[90, -20])
        source.set_gimbal(GimbalPose())
        self.assertEqual(home, source.render(100).tobytes())

    def test_camera_rejects_nonfinite_pose_before_publishing_it(self):
        source = SimulatedCameraSource(width=320, height=180)
        with self.assertRaises(ValueError):
            source.set_motion(self.motion(x_m=float("nan")))

    def test_compensated_camera_holds_world_image_during_body_rotation(self):
        source = SimulatedCameraSource(width=320, height=180)
        with unittest.mock.patch.object(source, "_draw_fenders"):
            source.set_view(self.motion(), GimbalPose())
            home = source.render(0).tobytes()
            body = self.motion(heading_deg=35, pitch_deg=8, roll_deg=12)
            source.set_view(body, GimbalPose())
            self.assertNotEqual(home, source.render(0).tobytes())
            source.set_view(body, GimbalPose(-35, -8, -12))
            self.assertEqual(home, source.render(0).tobytes())

    def test_direction_lock_keeps_rendered_aim_during_rover_turn_and_tilt(self):
        source = SimulatedCameraSource(width=320, height=180)
        gimbal = VirtualGimbal()
        gimbal.nudge(yaw=20, pitch=6)
        gimbal.set_stabilization_mode(StabilizationMode.LOCK)
        with unittest.mock.patch.object(source, "_draw_fenders"):
            source.set_view(self.motion(), gimbal.state)
            original = source.render(0).tobytes()
            gimbal.update_attitude(70, 11, 9)
            source.set_view(self.motion(heading_deg=70, pitch_deg=11, roll_deg=9), gimbal.state)
            self.assertEqual(original, source.render(0).tobytes())

    def test_follow_mode_turns_rendered_view_but_keeps_pitch_and_horizon(self):
        source = SimulatedCameraSource(width=320, height=180)
        gimbal = VirtualGimbal()
        gimbal.nudge(yaw=20, pitch=6)
        gimbal.set_stabilization_mode(StabilizationMode.FOLLOW)
        with unittest.mock.patch.object(source, "_draw_fenders"):
            source.set_view(self.motion(), gimbal.state)
            original = source.render(0).tobytes()
            gimbal.update_attitude(70, 11, 9)
            source.set_view(self.motion(heading_deg=70, pitch_deg=11, roll_deg=9), gimbal.state)
            followed = source.render(0).tobytes()
            self.assertNotEqual(original, followed)
            source.set_view(self.motion(heading_deg=70), GimbalPose(20, 6))
            self.assertEqual(followed, source.render(0).tobytes())

    def test_roll_keeps_frame_dimensions_and_atomic_view_copies_inputs(self):
        source = SimulatedCameraSource(width=320, height=180)
        body = self.motion(roll_deg=15)
        source.set_view(body, GimbalPose())
        image = source.render(0)
        self.assertEqual(image.size, (320, 180))
        body.roll_deg = 0
        self.assertEqual(image.tobytes(), source.render(0).tobytes())
        with self.assertRaises(ValueError):
            source.set_view(self.motion(), GimbalPose(roll_deg=float("nan")))

    def test_roll_overscan_avoids_empty_borders(self):
        image = Image.new("RGB", (320, 180), (40, 80, 120))
        for angle in (-45, -15, 15, 45):
            with self.subTest(angle=angle):
                rotated = SimulatedCameraSource._apply_roll(image, angle)
                self.assertEqual(rotated.size, image.size)
                self.assertEqual(rotated.getextrema(), ((40, 40), (80, 80), (120, 120)))

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
