"""Composition root: input -> controller model -> viewer, at 60 updates/sec."""

import argparse
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from pygame._sdl2 import controller as sdl

from .controller import PS4Controller
from .inputs import InputSource, KeyboardInput, PygamePS4Input
from .viewer import ControllerViewer, SIZE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PING PS4 controller input viewer")
    parser.add_argument("--demo", action="store_true", help="use keyboard input instead of hardware")
    parser.add_argument("--list-devices", action="store_true", help="print available SDL devices and exit")
    parser.add_argument("--device-index", type=int, help="select a mapped SDL device by index")
    parser.add_argument("--deadzone", type=float, default=0.10, help="radial stick deadzone, default 0.10")
    args = parser.parse_args(argv)
    if not 0.0 <= args.deadzone < 1.0:
        parser.error("--deadzone must be between 0 (inclusive) and 1 (exclusive)")
    if args.device_index is not None and args.device_index < 0:
        parser.error("--device-index must be nonnegative")

    source: InputSource | None = None
    try:
        pygame.display.init()
        pygame.font.init()
        pygame.joystick.init()
        sdl.init()
        if args.list_devices:
            if not sdl.get_count():
                print("No controllers detected. Connect USB or pair Bluetooth, then retry.")
            for index in range(sdl.get_count()):
                joystick = pygame.joystick.Joystick(index)
                print(f"{index}: {joystick.get_name()} | SDL mapped: {sdl.is_controller(index)} | GUID: {joystick.get_guid()}")
                joystick.quit()
            return 0
        surface = pygame.display.set_mode(SIZE)
        pygame.display.set_caption("PING | PS4 controller input")
        source = KeyboardInput() if args.demo else PygamePS4Input(args.device_index)
        controller = PS4Controller(args.deadzone)
        viewer = ControllerViewer()
        clock = pygame.time.Clock()
        # Seed the connection before processing user input. Attachment does not
        # synthesize presses for buttons that were already held.
        pygame.event.pump()
        controller.update(source.read(()))
        while True:
            events = pygame.event.get()
            if any(event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ) for event in events):
                break
            state = controller.update(source.read(events))
            # Future command handling can consume this same immutable snapshot.
            viewer.render(surface, state, source.status, args.demo)
            pygame.display.flip()
            clock.tick(60)
        return 0
    except pygame.error as exc:
        print(f"Unable to initialize controller viewer: {exc}")
        return 1
    finally:
        if source is not None:
            source.close()
        sdl.quit()
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
