"""Filter effects, sensitivity, caching and source preservation without hardware."""

import unittest
from unittest.mock import patch

import cv2
import numpy as np

from ping_base.camera import CameraFrame
from ping_base.camera_filters import CameraFilterSettings, CameraFrameProcessor, FILTER_LABELS, VISION_EFFECTS, apply_filters
from ping_base.dashboard import horizon_overlay


class CameraFilterTests(unittest.TestCase):
    def setUp(self):
        self.image = np.full((180, 320, 3), 60, np.uint8)
        cv2.rectangle(self.image, (60, 40), (130, 145), (90, 90, 90), -1)
        cv2.rectangle(self.image, (190, 55), (250, 130), (220, 220, 220), -1)
        ok, encoded = cv2.imencode(".jpg", self.image)
        self.assertTrue(ok)
        self.frame = CameraFrame(encoded.tobytes(), 1, 10, 320, 180)
        self.processor = CameraFrameProcessor()

    def test_normal_and_zero_opacity_return_the_original_jpeg(self):
        self.assertIs(self.processor.process(self.frame, CameraFilterSettings()), self.frame.jpeg)
        self.assertIs(self.processor.process(self.frame, CameraFilterSettings(view="edges", opacity=0)), self.frame.jpeg)

    def test_rotation_cycles_clockwise_without_modifying_source(self):
        image = np.arange(18, dtype=np.uint8).reshape(2, 3, 3)
        original = image.copy()
        for angle, turns in ((0, 0), (90, 3), (180, 2), (270, 1)):
            result = apply_filters(image, CameraFilterSettings(rotation=angle))
            np.testing.assert_array_equal(result, np.rot90(original, turns))
        np.testing.assert_array_equal(image, original)
        self.assertIsNot(self.processor.process(self.frame, CameraFilterSettings(rotation=180)), self.frame.jpeg)

    def test_edges_overlay_only_changes_edges_and_preserves_input(self):
        original = self.image.copy()
        result = apply_filters(self.image, CameraFilterSettings(view="edges", opacity=100))
        changed = np.any(result != self.image, axis=2)
        self.assertGreater(np.count_nonzero(changed), 0)
        self.assertLess(np.count_nonzero(changed), self.image.shape[0] * self.image.shape[1] // 10)
        np.testing.assert_array_equal(result[changed][0], (90, 220, 245))
        np.testing.assert_array_equal(result[0, 0], self.image[0, 0])
        np.testing.assert_array_equal(self.image, original)

    def test_higher_sensitivity_reveals_the_fainter_rectangle(self):
        low = apply_filters(self.image, CameraFilterSettings(view="edges", sensitivity=0))
        high = apply_filters(self.image, CameraFilterSettings(view="edges", sensitivity=100))
        self.assertGreater(np.count_nonzero(high != self.image), np.count_nonzero(low != self.image))

    def test_opacity_controls_line_strength_without_dimming_background(self):
        faint = apply_filters(self.image, CameraFilterSettings(view="edges", opacity=20)).astype(float)
        strong = apply_filters(self.image, CameraFilterSettings(view="edges", opacity=80)).astype(float)
        self.assertGreater(np.linalg.norm(strong - self.image), np.linalg.norm(faint - self.image))
        np.testing.assert_array_equal(faint[0, 0], strong[0, 0])

    def test_clahe_improves_local_contrast_and_preserves_dimensions(self):
        gradient = np.tile(np.linspace(90, 110, 320, dtype=np.uint8), (180, 1))
        image = cv2.cvtColor(gradient, cv2.COLOR_GRAY2BGR)
        result = apply_filters(image, CameraFilterSettings(view="contrast"))
        self.assertEqual(result.shape, image.shape)
        self.assertGreater(result.std(), image.std())

    def test_noise_reduction_and_sharpening_can_be_combined(self):
        noise = np.random.default_rng(7).integers(80, 120, (180, 320, 3), dtype=np.uint8)
        softened = apply_filters(noise, CameraFilterSettings(denoise=True))
        self.assertLess(softened.std(), noise.std())
        soft = cv2.GaussianBlur(self.image, (9, 9), 2)
        sharp = apply_filters(soft, CameraFilterSettings(sharpen=True))
        self.assertGreater(cv2.Laplacian(sharp, cv2.CV_64F).var(), cv2.Laplacian(soft, cv2.CV_64F).var())
        result = apply_filters(noise, CameraFilterSettings(view="edges", denoise=True, sharpen=True))
        self.assertEqual(result.shape, noise.shape)

    def test_contrast_and_edges_are_independent_and_stack_together(self):
        contrast = apply_filters(self.image, CameraFilterSettings(contrast=True))
        stacked = apply_filters(self.image, CameraFilterSettings(contrast=True, edges=True, opacity=100))
        changed = np.any(stacked != contrast, axis=2)
        self.assertGreater(np.count_nonzero(changed), 0)
        self.assertLess(np.count_nonzero(changed), changed.size // 10)
        np.testing.assert_array_equal(stacked[changed][0], (90, 220, 245))
        np.testing.assert_array_equal(stacked[~changed], contrast[~changed])

    def test_inversion_is_exact_and_does_not_modify_source(self):
        original = self.image.copy()
        result = apply_filters(self.image, CameraFilterSettings(invert=True))
        np.testing.assert_array_equal(result, 255 - original)
        np.testing.assert_array_equal(self.image, original)
        self.assertNotEqual(self.processor.process(self.frame, CameraFilterSettings(invert=True)), self.frame.jpeg)

    def test_vision_effects_each_change_the_image_and_mix_zero_is_passthrough(self):
        for name in VISION_EFFECTS:
            with self.subTest(effect=name):
                settings = CameraFilterSettings(**{name: True}, vision_strength=100)
                result = apply_filters(self.image, settings)
                self.assertEqual(result.shape, self.image.shape)
                self.assertEqual(result.dtype, np.uint8)
                self.assertFalse(np.array_equal(result, self.image))
                disabled = CameraFilterSettings(**{name: True}, vision_strength=0)
                self.assertIs(self.processor.process(self.frame, disabled), self.frame.jpeg)
        green = apply_filters(self.image, CameraFilterSettings(night_vision=True, vision_strength=100))
        self.assertGreater(green[:, :, 1].mean(), green[:, :, 0].mean())
        amber = apply_filters(self.image, CameraFilterSettings(amber=True, vision_strength=100))
        self.assertGreater(amber[:, :, 2].mean(), amber[:, :, 0].mean())

    def test_multiple_vision_effects_blend_without_turning_each_other_off(self):
        mixed = apply_filters(self.image, CameraFilterSettings(night_vision=True, amber=True))
        green = apply_filters(self.image, CameraFilterSettings(night_vision=True))
        amber = apply_filters(self.image, CameraFilterSettings(amber=True))
        self.assertFalse(np.array_equal(mixed, green))
        self.assertFalse(np.array_equal(mixed, amber))

    def test_scanlines_are_deterministic_and_only_darken_every_third_row(self):
        settings = CameraFilterSettings(scanlines=True)
        result = apply_filters(self.image, settings)
        np.testing.assert_array_equal(result[0::3], self.image[0::3])
        np.testing.assert_array_equal(result[2::3], self.image[2::3])
        self.assertTrue(np.all(result[1::3] < self.image[1::3]))
        np.testing.assert_array_equal(result, apply_filters(self.image, settings))

    def test_every_filter_can_run_in_a_single_stack_without_mutating_source(self):
        original = self.image.copy()
        settings = CameraFilterSettings(**dict.fromkeys(FILTER_LABELS, True))
        result = apply_filters(self.image, settings)
        self.assertEqual(result.shape, original.shape)
        self.assertEqual(result.dtype, np.uint8)
        self.assertFalse(np.array_equal(result, original))
        np.testing.assert_array_equal(self.image, original)
        encoded = self.processor.process(self.frame, settings)
        self.assertEqual(cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR).shape, original.shape)

    def test_new_filter_flags_and_mix_are_validated(self):
        for name in FILTER_LABELS:
            with self.subTest(effect=name), self.assertRaises(ValueError):
                CameraFilterSettings(**{name: "true"})
        for invalid in (-1, 101, True, float("nan")):
            with self.subTest(mix=invalid), self.assertRaises(ValueError):
                CameraFilterSettings(vision_strength=invalid)

    def test_processed_jpeg_is_cached_and_new_frames_clear_cache(self):
        settings = CameraFilterSettings(view="edges")
        with patch("ping_base.camera_filters.apply_filters", wraps=apply_filters) as filtering:
            first = self.processor.process(self.frame, settings)
            self.assertIs(first, self.processor.process(self.frame, settings))
            self.assertEqual(filtering.call_count, 1)
            decoded = cv2.imdecode(np.frombuffer(first, np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(decoded.shape, self.image.shape)
            next_frame = CameraFrame(self.frame.jpeg, 2, 11, 320, 180)
            self.processor.process(next_frame, settings)
            self.assertEqual(filtering.call_count, 2)

    def test_cache_is_bounded_as_sliders_change(self):
        for sensitivity in range(12):
            self.processor.process(self.frame, CameraFilterSettings(view="edges", sensitivity=sensitivity))
        self.assertLessEqual(len(self.processor._cache), self.processor.CACHE_LIMIT)

    def test_bad_settings_and_bad_jpegs_are_rejected(self):
        for values in ({"view": "bad"}, {"sensitivity": -1}, {"opacity": 101}, {"opacity": float("nan")}, {"denoise": "true"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                CameraFilterSettings(**values)
        bad = CameraFrame(b"not an image", 1, 10, 320, 180)
        with self.assertRaises(ValueError):
            self.processor.process(bad, CameraFilterSettings(view="contrast"))

    def test_horizon_tracks_camera_attitude_and_rejects_nonfinite_values(self):
        self.assertIn('rotate(-12.00) translate(0 30.00)', horizon_overlay(10, 12))
        self.assertEqual(horizon_overlay(float("nan"), 0), "")


if __name__ == "__main__":
    unittest.main()
