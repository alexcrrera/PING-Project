"""Service ownership and command routing without GUI, devices, or ports."""

from contextlib import redirect_stderr
from io import StringIO
import threading
import unittest
from unittest.mock import patch

from ping_base.cli import main
from ping_base.controller import Button, ControllerState, PS4Controller, RawInput
from ping_base.gimbal import StabilizationMode
from ping_base.station import BaseStation, NoController, PS4ControllerService


class FakeService:
    def __init__(self, name, events, *, start_error=None, close_error=None):
        self.name, self.events = name, events
        self.start_error, self.close_error = start_error, close_error
        self.state = ControllerState()
        self.status = "Fake service"

    def start(self):
        self.events.append((self.name, "start"))
        if self.start_error:
            raise self.start_error

    def update(self):
        self.events.append((self.name, "update"))
        return self.state

    def close(self):
        self.events.append((self.name, "close"))
        if self.close_error:
            raise self.close_error


class StationTests(unittest.TestCase):
    def make_station(self, *, camera_start_error=None, controller_start_error=None,
                     controller_close_error=None, camera_close_error=None):
        self.events = []
        self.telemetry = FakeService("telemetry", self.events)
        self.camera = FakeService("camera", self.events,
                                  start_error=camera_start_error,
                                  close_error=camera_close_error)
        self.controller = FakeService("controller", self.events,
                                      start_error=controller_start_error,
                                      close_error=controller_close_error)
        return BaseStation(self.telemetry, self.camera, self.controller)

    def test_devices_are_started_once_and_ticked_once_globally(self):
        station = self.make_station()
        station.tick()
        self.assertEqual(self.events, [])
        self.assertFalse(station.started)
        station.start()
        station.start()  # More dashboard clients must not acquire more devices.
        self.assertEqual(self.events, [("camera", "start"), ("controller", "start")])
        self.assertTrue(station.started)
        station.tick()
        self.assertEqual(self.events[-2:], [("controller", "update"), ("telemetry", "update")])
        # Camera capture has its own bounded producer and is not polled here.
        self.assertNotIn(("camera", "update"), self.events)
        station.close()
        self.assertFalse(station.started)
        self.assertEqual(self.events[-3:], [
            ("controller", "close"), ("camera", "close"), ("telemetry", "close"),
        ])
        after_close = tuple(self.events)
        station.tick()
        self.assertEqual(tuple(self.events), after_close)
        station.close()
        self.assertEqual(tuple(self.events), after_close)
        with self.assertRaisesRegex(RuntimeError, "cannot restart"):
            station.start()

    def test_default_input_is_explicitly_disabled_and_neutral(self):
        events = []
        station = BaseStation(FakeService("telemetry", events), FakeService("camera", events))
        self.assertIsInstance(station.controller, NoController)
        station.start()
        station.tick()
        state = station.controller.state
        self.assertFalse(state.connected)
        self.assertFalse(any(value.held for value in state.buttons.values()))
        self.assertIn("disabled", station.controller.status.lower())
        station.close()

    def test_stabilization_cycles_all_modes_for_a_gimbal_camera(self):
        station = self.make_station()
        self.camera.set_gimbal = lambda pose: None
        self.assertEqual(station.gimbal.stabilization_mode, StabilizationMode.OFF)
        for expected in (StabilizationMode.LOCK, StabilizationMode.FOLLOW,
                         StabilizationMode.OFF, StabilizationMode.LOCK):
            station.toggle_stabilization()
            self.assertEqual(station.gimbal.stabilization_mode, expected)
            self.assertEqual(station.gimbal.stabilized, expected != StabilizationMode.OFF)

    def test_stabilization_is_unavailable_without_a_camera_gimbal(self):
        station = self.make_station()
        for _ in range(4):
            station.toggle_stabilization()
            self.assertEqual(station.gimbal.stabilization_mode, StabilizationMode.OFF)

    def test_dualshock_touchpad_advances_map_sequence_once_per_press(self):
        station = self.make_station()
        model = PS4Controller()
        station.set_drive_mode("dualshock")
        station.start()

        def tick(held=False, *, connected=True):
            self.controller.state = model.update(RawInput(
                connected=connected, device_id="pad",
                held=frozenset({Button.TOUCHPAD}) if held else frozenset(),
                touchpad_available=True,
            ))
            station.tick()

        self.assertEqual(station.map_toggle_sequence, 0)
        tick(True)  # Attaching with the pad already held seeds its state.
        self.assertEqual(station.map_toggle_sequence, 0)
        tick(False)
        tick(True)
        self.assertEqual(station.map_toggle_sequence, 1)
        station.tick()  # Re-reading an immutable snapshot cannot replay its edge.
        self.assertEqual(station.map_toggle_sequence, 1)
        tick(True)
        tick(True)
        self.assertEqual(station.map_toggle_sequence, 1)
        tick(False)
        tick(True)
        self.assertEqual(station.map_toggle_sequence, 2)
        tick(connected=False)
        tick(True)  # Reconnection with the pad held is still not a press.
        self.assertEqual(station.map_toggle_sequence, 2)
        station.close()

    def test_map_touchpad_requires_selected_dualshock_mode_not_virtual_driving(self):
        station = self.make_station()
        model = PS4Controller()
        station.start()
        self.controller.state = model.update(RawInput(connected=True, device_id="pad"))
        station.tick()
        self.controller.state = model.update(RawInput(
            connected=True, device_id="pad", held=frozenset({Button.TOUCHPAD}),
        ))
        station.tick()
        self.assertEqual(station.map_toggle_sequence, 0)
        station.set_drive_mode("dualshock")
        station.tick()  # Switching modes cannot replay the previous keyboard-mode edge.
        self.assertEqual(station.map_toggle_sequence, 0)
        self.controller.state = model.update(RawInput(connected=True, device_id="pad"))
        station.tick()
        self.controller.state = model.update(RawInput(
            connected=True, device_id="pad", held=frozenset({Button.TOUCHPAD}),
        ))
        station.tick()
        self.assertFalse(station.virtual_driving)  # USB/fake telemetry must not disable map access.
        self.assertEqual(station.map_toggle_sequence, 1)
        station.close()

    def test_partial_startup_failure_releases_every_service(self):
        for failing_service in ("camera", "controller"):
            with self.subTest(service=failing_service):
                error = RuntimeError("startup failed")
                station = self.make_station(**{f"{failing_service}_start_error": error})
                with self.assertRaisesRegex(RuntimeError, "startup failed"):
                    station.start()
                self.assertFalse(station.started)
                self.assertEqual(self.events[-3:], [
                    ("controller", "close"), ("camera", "close"), ("telemetry", "close"),
                ])
                station.tick()
                self.assertFalse(any(event[1] == "update" for event in self.events))

    def test_cleanup_continues_when_controller_or_camera_close_fails(self):
        for failing_service in ("controller", "camera"):
            with self.subTest(service=failing_service):
                station = self.make_station(**{
                    f"{failing_service}_close_error": RuntimeError("cleanup failed"),
                })
                station.start()
                with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
                    station.close()
                self.assertFalse(station.started)
                self.assertEqual(self.events[-3:], [
                    ("controller", "close"), ("camera", "close"), ("telemetry", "close"),
                ])


class ControllerServiceTests(unittest.TestCase):
    def test_display_initialization_failure_releases_sdl_and_leaves_neutral_input(self):
        import pygame

        with patch("pygame.display.init", side_effect=pygame.error("No display")), \
                patch("pygame._sdl2.controller.quit") as sdl_quit, \
                patch("pygame.quit") as quit_pygame, \
                patch("ping_base.inputs.PygamePS4Input") as source:
            service = PS4ControllerService()
            service.start()
            self.assertFalse(service.state.connected)
            self.assertIsNone(service.source)
            self.assertIsNone(service._pygame)
            self.assertIn("No display", service.status)
            source.assert_not_called()
            sdl_quit.assert_called_once()
            quit_pygame.assert_called_once()

    def test_sdl_lifecycle_and_event_polling_stay_on_calling_thread(self):
        import pygame
        from ping_base.controller import Button, RawInput, Stick

        owner = threading.get_ident()
        calls = []
        readings = iter((
            RawInput(connected=True, device_id="test"),
            RawInput(connected=True, device_id="test", held=frozenset({Button.CROSS}),
                     left_stick=Stick(.6, 0)),
        ))

        class FakeInput:
            status = "Fake PS4 connected"

            def __init__(self, device_index):
                calls.append(("open", threading.get_ident(), device_index))

            def read(self, events):
                calls.append(("read", threading.get_ident(), tuple(events)))
                return next(readings)

            def close(self):
                calls.append(("close", threading.get_ident()))

        with patch("pygame.display.init"), patch("pygame.display.set_mode") as display, \
                patch("pygame.joystick.init"), patch("pygame.event.get", return_value=["event"]), \
                patch("pygame._sdl2.controller.quit") as sdl_quit, patch("pygame.quit") as quit_pygame, \
                patch("ping_base.inputs.PygamePS4Input", FakeInput):
            service = PS4ControllerService(device_index=2)
            service.start()
            service.start()  # Startup is idempotent.
            state = service.update()
            self.assertTrue(state.connected)
            self.assertTrue(state.buttons[Button.CROSS].pressed)
            self.assertEqual(service.status, "Fake PS4 connected")
            self.assertEqual(display.call_count, 1)
            self.assertEqual(display.call_args.args, ((1, 1), pygame.HIDDEN))
            service.close()
            self.assertFalse(service.state.connected)
            self.assertTrue(service.state.buttons[Button.CROSS].released)
            self.assertEqual(service.state.left_stick.x, 0)
            service.close()
            sdl_quit.assert_called_once()
            quit_pygame.assert_called_once()
        self.assertEqual([entry[0] for entry in calls], ["open", "read", "read", "close"])
        self.assertTrue(all(entry[1] == owner for entry in calls))
        self.assertEqual(calls[0][2], 2)
        self.assertEqual(calls[1][2], ("event",))


class CommandLineTests(unittest.TestCase):
    def test_invalid_arguments_fail_before_loading_gui_or_opening_devices(self):
        invalid = [
            ["--port", "0"], ["--port", "65536"], ["--baud", "0"],
            ["--deadzone", "nan"], ["--deadzone", "inf"], ["--deadzone", "-.1"],
            ["--deadzone", "1"], ["--device-index", "-1"], ["--device-index", "0"],
            ["--serial-port", "   "],
        ]
        for args in invalid:
            with self.subTest(args=args), redirect_stderr(StringIO()) as output:
                with self.assertRaises(SystemExit) as raised:
                    main(args)
                self.assertEqual(raised.exception.code, 2)
                self.assertIn("error:", output.getvalue())

    def test_legacy_viewer_and_device_listing_route_to_existing_diagnostics(self):
        with patch("ping_base.app.main", return_value=23) as diagnostics:
            self.assertEqual(main(["--controller-viewer", "--demo", "--deadzone", ".2"]), 23)
            diagnostics.assert_called_once_with(["--demo", "--deadzone", ".2"])
        with patch("ping_base.app.main", return_value=0) as diagnostics:
            self.assertEqual(main(["--list-devices"]), 0)
            diagnostics.assert_called_once_with(["--list-devices"])


if __name__ == "__main__":
    unittest.main()
