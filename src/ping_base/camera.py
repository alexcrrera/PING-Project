"""Replaceable camera adapters with a cached frame and no UI-thread capture.

``SimulatedCameraSource`` needs Pillow only. ``OpenCVCameraSource`` keeps the
hardware driver in a separate process: even a wedged USB driver cannot stall
HTTP requests, telemetry updates, or application shutdown.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from io import BytesIO
import math
import multiprocessing as mp
import queue
import random
import threading
import time
from typing import Any, Protocol

from PIL import Image, ImageDraw


@dataclass(frozen=True, slots=True)
class CameraFrame:
    jpeg: bytes
    sequence: int
    captured_at: float
    width: int
    height: int


class CameraSource(Protocol):
    """A future network camera can implement this same small interface."""

    name: str
    simulated: bool

    @property
    def status(self) -> str: ...

    @property
    def error(self) -> str | None: ...

    def start(self) -> None: ...

    def latest_frame(self) -> CameraFrame | None: ...

    def close(self) -> None: ...


class CameraMotion(Protocol):
    """Only pose crosses from the simulation loop to the camera worker."""

    x_m: float
    y_m: float
    heading_deg: float
    pitch_deg: float
    roll_deg: float


@dataclass(frozen=True, slots=True)
class _CameraPose:
    x_m: float
    y_m: float
    heading_deg: float
    pitch_deg: float
    roll_deg: float


class _LatestFrameSource(ABC):
    """One capture producer, any number of cheap latest-frame readers."""

    def __init__(self, *, width: int, height: int, fps: float) -> None:
        if width < 160 or height < 90 or not math.isfinite(fps) or not 0 < fps <= 60:
            raise ValueError("Camera needs width >= 160, height >= 90 and 0 < fps <= 60")
        self.width, self.height, self.fps = width, height, fps
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame: CameraFrame | None = None
        self._error: str | None = None
        self._status = "Stopped"

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def error(self) -> str | None:
        with self._lock:
            return self._error

    def latest_frame(self) -> CameraFrame | None:
        with self._lock:
            return self._frame

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        with self._lock:
            self._error = None
            self._frame = None
            self._status = "Connecting"
        try:
            self._open()
        except Exception as exc:
            self._fail(exc)
            self._close()
            return
        self._thread = threading.Thread(target=self._run, name=f"camera-{self.name}", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._close()
        with self._lock:
            self._status = "Stopped"

    def _fail(self, exc: Exception) -> None:
        with self._lock:
            self._error = str(exc)
            self._status = "Unavailable"

    def _run(self) -> None:
        sequence = 0
        period = 1.0 / self.fps
        try:
            while not self._stop.is_set():
                began = time.monotonic()
                try:
                    result = self._capture_frame(began)
                    if result is not None:
                        jpeg, width, height, captured_at = result
                        sequence += 1
                        with self._lock:
                            self._frame = CameraFrame(jpeg, sequence, captured_at, width, height)
                            self._status = "Simulation" if self.simulated else "Connected"
                except Exception as exc:
                    self._fail(exc)
                    break
                self._stop.wait(max(0.0, period - (time.monotonic() - began)))
        finally:
            self._close()

    def _open(self) -> None:
        pass

    def _close(self) -> None:
        pass

    @abstractmethod
    def _capture_frame(self, now: float) -> tuple[bytes, int, int, float] | None:
        """Return one frame; adapters must keep this operation bounded."""


class SimulatedCameraSource(_LatestFrameSource):
    """A moving, deterministic grayscale test terrain, clearly a simulation.

    The frame deliberately contains no aiming/status graphics: those belong to
    the dashboard overlay so a real camera gets exactly the same instrument UI.
    """

    name = "Virtual terrain"
    simulated = True

    def __init__(self, *, width: int = 960, height: int = 540, fps: float = 12, seed: int = 7) -> None:
        super().__init__(width=width, height=height, fps=fps)
        rng = random.Random(seed)
        self._rocks = [
            (rng.uniform(-17, 17), rng.uniform(4, 90), rng.uniform(.15, 1.1), rng.randrange(8))
            for _ in range(62)
        ]
        self._pebbles = [(rng.uniform(-22, 22), rng.uniform(2, 90), rng.uniform(.012, .07)) for _ in range(460)]
        self._began = time.monotonic()
        self._background = self._make_background(rng)
        self._seed = seed
        self._motion_lock = threading.Lock()
        self._motion: _CameraPose | None = None
        self._terrain_cache: OrderedDict[tuple[int, int], tuple[list, list]] = OrderedDict()
        self._panorama = self._make_panorama(random.Random(seed + 101))

    def set_motion(self, motion: CameraMotion | None) -> None:
        """Bind a pose without doing image work on the station's control thread.

        Heading zero points along world +y; positive angles turn clockwise.
        Passing ``None`` restores the independent ambient camera demonstration.
        """
        pose = None if motion is None else _CameraPose(
            float(motion.x_m), float(motion.y_m), float(motion.heading_deg),
            float(motion.pitch_deg), float(motion.roll_deg),
        )
        if pose is not None and not all(math.isfinite(value) for value in
                                       (pose.x_m, pose.y_m, pose.heading_deg,
                                        pose.pitch_deg, pose.roll_deg)):
            raise ValueError("Camera motion must contain finite pose values")
        with self._motion_lock:
            self._motion = pose

    def _open(self) -> None:
        self._began = time.monotonic()

    def _make_background(self, rng: random.Random) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        horizon = self.height * .405
        for y in range(self.height):
            if y < horizon:
                t = y / horizon
                tone = round(115 + 38 * t)
            else:
                t = (y - horizon) / (self.height - horizon)
                tone = round(91 - 29 * t)
            draw.line((0, y, self.width, y), fill=(tone, tone + 2, tone))
        # Three separated ridgelines give distant scale without a photographic
        # asset, network request or a misleading prerecorded "live" feed.
        for ridge, color in ((.145, (115, 118, 114)), (.105, (103, 106, 102)), (.065, (91, 95, 90))):
            points: list[tuple[float, float]] = [(-40, horizon + 10)]
            x = -40.0
            while x <= self.width + 60:
                points.append((x, horizon - self.height * ridge * rng.uniform(.35, 1)))
                x += rng.uniform(24, 82) * self.width / 960
            points.extend([(self.width + 60, horizon + 16), (-40, horizon + 16)])
            draw.polygon(points, fill=color)
        return image

    def _make_panorama(self, rng: random.Random) -> Image.Image:
        """Cache a seamless distant horizon for looking around the test site."""
        width, height = self.width * 4, self.height
        image = self._background.resize((width, height))
        draw = ImageDraw.Draw(image)
        horizon = height * .405
        # Fill the old ridge area before adding periodic ridgelines.
        for y in range(height):
            t = y / horizon if y < horizon else (y - horizon) / (height - horizon)
            tone = round(115 + 38 * t) if y < horizon else round(91 - 29 * t)
            draw.line((0, y, width, y), fill=(tone, tone + 2, tone))
        count = 64
        for ridge, color in ((.145, (115, 118, 114)), (.105, (103, 106, 102)),
                             (.065, (91, 95, 90))):
            heights = [horizon - height * ridge * rng.uniform(.35, 1) for _ in range(count)]
            points = [(index * width / count, heights[index % count]) for index in range(count + 1)]
            draw.polygon(points + [(width, horizon + 16), (0, horizon + 16)], fill=color)
        panorama = Image.new("RGB", (width + self.width, height))
        panorama.paste(image)
        panorama.paste(image.crop((0, 0, self.width, height)), (width, 0))
        return panorama

    def _terrain_chunk(self, cx: int, cy: int) -> tuple[list, list]:
        key = (cx, cy)
        if key in self._terrain_cache:
            self._terrain_cache.move_to_end(key)
            return self._terrain_cache[key]
        # Integer arithmetic makes a site's obstacles identical when returning
        # after a long drive, without retaining an ever-growing world in memory.
        rng = random.Random(self._seed ^ (cx * 73856093) ^ (cy * 19349663))
        rocks, pebbles = [], []
        for _ in range(10):
            x, y = cx * 32 + rng.uniform(0, 32), cy * 32 + rng.uniform(0, 32)
            if abs(x) > 2.5:
                rocks.append((x, y, rng.uniform(.15, 1.1), rng.randrange(8)))
        for _ in range(85):
            pebbles.append((cx * 32 + rng.uniform(0, 32), cy * 32 + rng.uniform(0, 32),
                            rng.uniform(.012, .07)))
        self._terrain_cache[key] = (rocks, pebbles)
        while len(self._terrain_cache) > 100:
            self._terrain_cache.popitem(last=False)
        return rocks, pebbles

    @staticmethod
    def _clip_near(points: list[tuple[float, float]], near: float = .75) -> list[tuple[float, float]]:
        """Clip a ground polygon before projection, including when facing away."""
        result = []
        previous = points[-1]
        for current in points:
            if (current[1] >= near) != (previous[1] >= near):
                fraction = (near - previous[1]) / (current[1] - previous[1])
                result.append((previous[0] + fraction * (current[0] - previous[0]), near))
            if current[1] >= near:
                result.append(current)
            previous = current
        return result

    def _render_motion(self, pose: _CameraPose) -> Image.Image:
        """Project a fixed local world through the moving rover-mounted camera."""
        w, h = self.width, self.height
        offset = round((pose.heading_deg % 360) / 360 * w * 4)
        image = self._panorama.crop((offset, 0, offset + w, h))
        draw = ImageDraw.Draw(image)
        focal, horizon = w * .71, h * .405
        angle = math.radians(pose.heading_deg)
        cosine, sine = math.cos(angle), math.sin(angle)

        def local(x: float, y: float) -> tuple[float, float]:
            dx, dy = x - pose.x_m, y - pose.y_m
            return dx * cosine - dy * sine, dx * sine + dy * cosine

        def project(x: float, depth: float, z: float = 0) -> tuple[float, float]:
            return w * .5 + x * focal / depth, horizon + (1.12 - z) * focal / depth

        # The lane and its markers are world fixtures: reverse retraces the
        # image, and steering naturally moves the lane out of the camera view.
        def ground_strip(x1: float, x2: float, color: tuple[int, int, int]) -> None:
            points = self._clip_near([local(x, pose.y_m + y) for x, y in
                                      ((x1, -140), (x2, -140), (x2, 140), (x1, 140))])
            if len(points) >= 3:
                draw.polygon([project(*point) for point in points], fill=color)

        ground_strip(-1.8, 1.8, (85, 89, 83))
        for side in (-1, 1):
            for delta in (-.09, .09):
                ground_strip(side * .89 + delta - .012, side * .89 + delta + .012, (67, 72, 66))

        objects: list[tuple[float, str, Any]] = []
        cx, cy = math.floor(pose.x_m / 32), math.floor(pose.y_m / 32)
        for tile_x in range(cx - 3, cx + 4):
            for tile_y in range(cy - 3, cy + 4):
                rocks, pebbles = self._terrain_chunk(tile_x, tile_y)
                for x, y, radius in pebbles:
                    right, depth = local(x, y)
                    if .75 < depth < 100 and abs(right) < depth:
                        px, py = project(right, depth)
                        r = max(.6, radius * focal / depth)
                        if -r < px < w + r and horizon < py < h + r:
                            draw.ellipse((px - r, py - r * .35, px + r, py + r * .45), fill=(64, 69, 63))
                for x, y, size, variant in rocks:
                    right, depth = local(x, y)
                    if .75 < depth < 100 and abs(right) < depth + size:
                        objects.append((depth, "rock", (right, size, variant)))
        for index in range(math.floor((pose.y_m - 110) / 11), math.ceil((pose.y_m + 110) / 11)):
            right, depth = local(-2.45 if index % 2 else 2.45, index * 11)
            if 1 < depth < 100 and abs(right) < depth:
                objects.append((depth, "marker", (right,)))
        self._draw_solids(draw, project, objects)
        self._draw_fenders(draw)
        return image

    def _draw_fenders(self, draw: ImageDraw.ImageDraw) -> None:
        w, h = self.width, self.height
        draw.polygon([(0, h), (0, h * .87), (w * .13, h * .93), (w * .20, h)], fill=(33, 38, 33))
        draw.polygon([(w, h), (w, h * .87), (w * .87, h * .93), (w * .80, h)], fill=(33, 38, 33))
        draw.line([(0, h * .87), (w * .13, h * .93), (w * .20, h)], fill=(112, 118, 109), width=2)
        draw.line([(w, h * .87), (w * .87, h * .93), (w * .80, h)], fill=(112, 118, 109), width=2)

    def _draw_solids(self, draw: ImageDraw.ImageDraw, project: Any,
                     objects: list[tuple[float, str, Any]]) -> None:
        w, h, focal = self.width, self.height, self.width * .71
        for distance, kind, attributes in sorted(objects, reverse=True):
            if kind == "marker":
                x = attributes[0]
                p = [project(x + dx, distance, z) for dx, z in
                     ((-.035, 0), (.035, 0), (.035, 1.1), (-.035, 1.1))]
                draw.polygon(p, fill=(168, 171, 161))
                draw.line((project(x, distance, .5), project(x, distance, .78)),
                          fill=(53, 59, 52), width=max(1, round(focal * .07 / distance)))
                plate = [project(x + dx, distance, z) for dx, z in
                         ((-.17, .93), (.17, .93), (.17, 1.18), (-.17, 1.18))]
                draw.polygon(plate, fill=(179, 183, 173))
                continue
            x, size, variant = attributes
            px, py = project(x, distance)
            s = size * focal / distance
            if px < -2 * s or px > w + 2 * s or py > h + s:
                continue
            draw.ellipse((px - s * .8, py - s * .1, px + s * 1.45, py + s * .24), fill=(49, 55, 49))
            vertices = [(px - s, py), (px - s * .82, py - s * .45),
                        (px - s * .18, py - s * .73), (px + s * .46, py - s * .59),
                        (px + s * .9, py - s * .13), (px + s * .58, py + s * .10)]
            tone = 99 + variant * 3
            draw.polygon(vertices, fill=(tone, tone + 3, tone - 1))
            center = (px + s * .02, py - s * .20)
            draw.polygon([vertices[0], vertices[1], vertices[2], center], fill=(tone + 19, tone + 22, tone + 15))
            draw.polygon([vertices[2], vertices[3], vertices[4], center], fill=(tone + 8, tone + 11, tone + 5))
            draw.polygon([vertices[4], vertices[5], vertices[0], center], fill=(tone - 20, tone - 16, tone - 21))

    def render(self, elapsed: float) -> Image.Image:
        """Render a frame independently of the capture lifecycle (useful in previews)."""
        with self._motion_lock:
            pose = self._motion
        if pose is not None:
            return self._render_motion(pose)
        image = self._background.copy()
        draw = ImageDraw.Draw(image)
        w, h = self.width, self.height
        focal, horizon = w * .71, h * .405
        eye_height = 1.12
        sway = math.sin(elapsed * .11) * .12
        advance = elapsed * .34

        def project(x: float, distance: float, z: float = 0) -> tuple[float, float]:
            return (w * .5 + (x - sway) * focal / distance,
                    horizon + (eye_height - z) * focal / distance)

        # Compacted access lane with a soft irregular edge.
        left = [project(-1.8 + math.sin(d * .25) * .11, d) for d in (1, 2, 4, 8, 16, 32, 90)]
        right = [project(1.8 + math.sin(d * .19) * .13, d) for d in (90, 32, 16, 8, 4, 2, 1)]
        draw.polygon(left + right, fill=(85, 89, 83))
        # Four tire tracks expose perspective and forward motion at walking speed.
        for side in (-1, 1):
            for offset in (-.09, .09):
                points = [project(side * .89 + offset, d) for d in (1.1, 2, 4, 8, 16, 32, 90)]
                draw.line(points, fill=(67, 72, 66), width=max(1, round(w / 480)))
        for index in range(42):
            distance = 2 + ((index * 2.2 - advance) % 88)
            for side in (-1, 1):
                a = project(side * .89 - .14, distance)
                b = project(side * .89 + .14, distance + .04)
                draw.line((a, b), fill=(74, 79, 72), width=max(1, round(w / 700)))

        for x, original_d, radius in self._pebbles:
            distance = 2 + ((original_d - advance) % 88)
            px, py = project(x, distance)
            r = max(.6, radius * focal / distance)
            if -r < px < w + r and horizon < py < h + r:
                draw.ellipse((px - r, py - r * .35, px + r, py + r * .45), fill=(64, 69, 63))

        # Render far-to-near solids, including grounded shadows and faceted rocks.
        objects: list[tuple[float, str, Any]] = []
        for x, original_d, size, variant in self._rocks:
            distance = 4 + ((original_d - advance) % 86)
            if abs(x) < 2.5:
                x += math.copysign(2.6, x)
            objects.append((distance, "rock", (x, size, variant)))
        for index in range(8):
            distance = 7 + ((index * 11 - advance) % 86)
            objects.append((distance, "marker", (-2.45 if index % 2 else 2.45,)))
        self._draw_solids(draw, project, objects)
        self._draw_fenders(draw)
        return image

    def _capture_frame(self, now: float) -> tuple[bytes, int, int, float]:
        output = BytesIO()
        self.render(now - self._began).save(output, "JPEG", quality=86, optimize=False)
        return output.getvalue(), self.width, self.height, now


def _opencv_capture_loop(device: int | str, width: int, height: int, fps: float,
                         messages: Any, stop: Any) -> None:
    """Child-process entry point; never imports OpenCV for simulation mode."""
    capture = None

    def publish(message: tuple) -> None:
        try:
            messages.put_nowait(message)
        except queue.Full:
            try:
                messages.get_nowait()
            except queue.Empty:
                pass
            try:
                messages.put_nowait(message)
            except queue.Full:
                pass

    try:
        import cv2

        capture = cv2.VideoCapture(device)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open USB camera {device}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        failures = 0
        while not stop.is_set():
            began = time.monotonic()
            ok, frame = capture.read()
            if not ok or frame is None:
                failures += 1
                if failures >= 5:
                    raise RuntimeError("USB camera stopped returning frames")
                stop.wait(.1)
                continue
            failures = 0
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 86])
            if ok:
                publish(("frame", encoded.tobytes(), int(frame.shape[1]), int(frame.shape[0]), began))
            stop.wait(max(0.0, 1.0 / fps - (time.monotonic() - began)))
    except ImportError:
        publish(("error", "USB camera support needs the optional opencv-python package"))
    except Exception as exc:
        publish(("error", str(exc)))
    finally:
        if capture is not None:
            capture.release()


class OpenCVCameraSource(_LatestFrameSource):
    """Optional USB/IP camera with driver isolation and a bounded shutdown."""

    simulated = False

    def __init__(self, device: int | str = 0, *, width: int = 960, height: int = 540, fps: float = 12,
                 timeout: float = 8.0) -> None:
        super().__init__(width=width, height=height, fps=fps)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Camera timeout must be positive")
        self.device, self.timeout = device, timeout
        self.name = f"USB camera {device}" if isinstance(device, int) else "Network camera"
        self._process: mp.Process | None = None
        self._messages: Any = None
        self._capture_stop: Any = None
        self._last_received = 0.0

    def _open(self) -> None:
        context = mp.get_context("spawn")
        self._messages = context.Queue(maxsize=2)
        self._capture_stop = context.Event()
        self._process = context.Process(
            target=_opencv_capture_loop,
            args=(self.device, self.width, self.height, self.fps, self._messages, self._capture_stop),
            name="ping-camera-capture", daemon=True,
        )
        self._last_received = time.monotonic()
        self._process.start()

    def _capture_frame(self, now: float) -> tuple[bytes, int, int, float] | None:
        try:
            message = self._messages.get(timeout=.12)
        except queue.Empty:
            if self._process is not None and not self._process.is_alive():
                raise RuntimeError("Camera capture process exited")
            if now - self._last_received > self.timeout:
                raise RuntimeError(f"No camera frame received for {self.timeout:g} seconds")
            return None
        if message[0] == "error":
            raise RuntimeError(message[1])
        self._last_received = now
        return message[1], message[2], message[3], message[4]

    def _close(self) -> None:
        if self._capture_stop is not None:
            self._capture_stop.set()
        process = self._process
        if process is not None:
            process.join(timeout=.35)
            if process.is_alive():
                process.terminate()
                process.join(timeout=.35)
            if not process.is_alive():
                process.close()
            self._process = None
        if self._messages is not None:
            self._messages.cancel_join_thread()
            self._messages.close()
            self._messages = None

