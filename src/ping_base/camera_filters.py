"""Camera display filters, independent of capture and rover control services."""

from collections import OrderedDict
from dataclasses import dataclass
import threading

import cv2
import numpy as np

from .camera import CameraFrame


VIEW_MODES = {"normal": "Normal", "contrast": "Enhanced contrast", "edges": "Edge overlay"}
FILTER_LABELS = {
    "denoise": "Noise reduction", "contrast": "Enhanced contrast", "sharpen": "Sharpen details",
    "invert": "Invert colors", "night_vision": "Night vision green", "amber": "Amber phosphor",
    "white_phosphor": "White phosphor", "thermal": "Thermal style (simulated)",
    "edges": "Edge overlay", "scanlines": "Scanlines",
}
VISION_EFFECTS = ("night_vision", "amber", "white_phosphor", "thermal")
_LEVELS = np.linspace(0, 1, 256, dtype=np.float32)[:, None, None]
_VISION_PALETTES = {
    name: np.rint((np.sqrt(_LEVELS) if name == "night_vision" else _LEVELS)
                  * np.array(tint, dtype=np.float32) * 255).astype(np.uint8)
    for name, tint in {"night_vision": (.16, 1, .10), "amber": (.05, .67, 1),
                       "white_phosphor": (1, .97, .90)}.items()
}


@dataclass(frozen=True, slots=True)
class CameraFilterSettings:
    view: str = "normal"
    sensitivity: int = 50
    opacity: int = 65
    denoise: bool = False
    sharpen: bool = False
    contrast: bool = False
    edges: bool = False
    invert: bool = False
    night_vision: bool = False
    amber: bool = False
    white_phosphor: bool = False
    thermal: bool = False
    scanlines: bool = False
    vision_strength: int = 75
    rotation: int = 0

    def __post_init__(self) -> None:
        if self.rotation not in (0, 90, 180, 270):
            raise ValueError("Camera rotation must be 0, 90, 180 or 270 degrees")
        if self.view not in VIEW_MODES:
            raise ValueError("Choose a supported camera view")
        for value in (self.sensitivity, self.opacity, self.vision_strength):
            if type(value) is not int or not 0 <= value <= 100:
                raise ValueError("Camera filter controls must be integers from 0 to 100")
        if any(type(getattr(self, name)) is not bool for name in FILTER_LABELS):
            raise ValueError("Camera filter switches must be boolean")

    @property
    def contrast_enabled(self) -> bool:
        return self.contrast or self.view == "contrast"

    @property
    def edges_enabled(self) -> bool:
        return self.edges or self.view == "edges"

    @property
    def is_passthrough(self) -> bool:
        return not (self.rotation or self.denoise or self.sharpen or self.contrast_enabled or self.invert or self.scanlines
                    or self.edges_enabled and self.opacity > 0
                    or self.vision_strength > 0 and any(getattr(self, name) for name in VISION_EFFECTS))


def apply_filters(image: np.ndarray, settings: CameraFilterSettings) -> np.ndarray:
    """Return a filtered BGR image without modifying the source array."""
    result = image.copy()
    if settings.rotation:
        result = cv2.rotate(result, {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
                                     270: cv2.ROTATE_90_COUNTERCLOCKWISE}[settings.rotation])
    if settings.denoise:
        result = cv2.bilateralFilter(result, 5, 35, 35)
    if settings.contrast_enabled:
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    if settings.sharpen:
        blurred = cv2.GaussianBlur(result, (0, 0), 1.0)
        result = cv2.addWeighted(result, 1.6, blurred, -.6, 0)
    # Detect structure before recoloring so palettes can be stacked without
    # suppressing outlines. Draw the outlines after the entire color stack.
    edges = None
    if settings.edges_enabled and settings.opacity:
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        threshold = round(140 - settings.sensitivity * 1.2)
        edges = cv2.Canny(gray, threshold, threshold * 2, L2gradient=True) != 0

    alpha = settings.vision_strength / 100
    if alpha:
        for name in VISION_EFFECTS:
            if not getattr(settings, name):
                continue
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            if name == "thermal":
                styled = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
            else:
                styled = cv2.applyColorMap(gray, _VISION_PALETTES[name])
            result = cv2.addWeighted(result, 1 - alpha, styled, alpha, 0)
    if settings.invert:
        result = cv2.bitwise_not(result)
    if edges is not None:
        alpha = settings.opacity / 100
        # Warm yellow lines preserve the source everywhere outside an edge.
        result[edges] = np.rint(result[edges] * (1 - alpha) + np.array((90, 220, 245)) * alpha).astype(np.uint8)
    if settings.scanlines:
        result[1::3] = (result[1::3].astype(np.uint16) * 78 // 100).astype(np.uint8)
    return result


class CameraFrameProcessor:
    """Bounded, thread-safe cache used by the camera HTTP worker threads.

    Decoding happens once per source frame. Each viewer chooses its own settings;
    capture, telemetry, and the main UI event loop never run these filters.
    """

    CACHE_LIMIT = 8

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame_id: tuple[int, float] | None = None
        self._image: np.ndarray | None = None
        self._cache: OrderedDict[CameraFilterSettings, bytes] = OrderedDict()

    def process(self, frame: CameraFrame, settings: CameraFilterSettings) -> bytes:
        if settings.is_passthrough:
            return frame.jpeg
        with self._lock:
            frame_id = (frame.sequence, frame.captured_at)
            if frame_id != self._frame_id:
                decoded = cv2.imdecode(np.frombuffer(frame.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if decoded is None:
                    raise ValueError("Camera frame is not a valid JPEG")
                self._frame_id, self._image = frame_id, decoded
                self._cache.clear()
            if settings not in self._cache:
                result = apply_filters(self._image, settings)
                ok, encoded = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if not ok:
                    raise RuntimeError("Could not encode the camera view")
                self._cache[settings] = encoded.tobytes()
                while len(self._cache) > self.CACHE_LIMIT:
                    self._cache.popitem(last=False)
            self._cache.move_to_end(settings)
            return self._cache[settings]
