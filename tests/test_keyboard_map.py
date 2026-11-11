"""Run the real shortcut bridge with a small DOM substitute; no browser needed."""

import json
import shutil
import subprocess
import unittest

from ping_base.keyboard import KEYBOARD_SCRIPT


NODE = shutil.which("node")
HARNESS = r"""
const assert = require('node:assert/strict');
class Target {
    constructor() { this.listeners = new Map(); }
    addEventListener(type, listener, options = {}) {
        const entry = {listener, active:true};
        if (!this.listeners.has(type)) this.listeners.set(type, []);
        this.listeners.get(type).push(entry);
        options.signal?.addEventListener('abort', () => {entry.active = false;});
    }
    dispatch(type, event) {
        for (const entry of this.listeners.get(type) || []) if (entry.active) entry.listener(event);
    }
}
const target = kind => ({closest:selector => kind && selector.includes(kind) ? {} : null});
const document = new Target();
const window = new Target();
const events = [];
const dataset = {mode:'keyboard', enabled:'true', gimbal:'true', stabilization:'true'};
let focus = true;
let dialog = false;
let heartbeat;
document.hidden = false;
document.activeElement = target();
document.body = {classList:{contains:() => dialog}};
document.hasFocus = () => focus;
document.getElementById = () => ({dataset});
const emitEvent = (name, args) => events.push({name, args});
const setInterval = callback => {heartbeat = callback; return 1;};
const clearInterval = () => {};
const press = (properties = {}) => {
    const event = {code:'KeyM', repeat:false, ctrlKey:false, altKey:false, metaKey:false,
        target:target(), preventDefault(){this.prevented = true;}, stopPropagation(){this.stopped = true;}, ...properties};
    document.dispatch('keydown', event);
    return event;
};
const count = () => events.filter(event => event.name === 'map_toggle').length;
"""


@unittest.skipUnless(NODE, "Node is optional; required only to execute the browser shortcut bridge")
class KeyboardMapTests(unittest.TestCase):
    def test_stabilization_shortcut_works_without_virtual_camera(self):
        self.run_javascript("""
            dataset.gimbal = 'false';
            press({code:'KeyZ'});
            press({code:'KeyZ', repeat:true});
            assert.equal(events.filter(event => event.name === 'camera_stabilization').length, 1);
            dataset.stabilization = 'false';
            press({code:'KeyZ'});
            assert.equal(events.filter(event => event.name === 'camera_stabilization').length, 1);
        """)

    def test_zoom_keys_do_not_steer_and_shortcuts_do_not_repeat(self):
        self.run_javascript(r"""
            for (const [code, name] of [['ArrowRight','camera_zoom_in'],
                    ['ArrowLeft','camera_zoom_out'], ['Enter','map_zoom'],
                    ['KeyX','camera_home'], ['KeyZ','camera_stabilization'], ['KeyB','drive_brake_toggle']]) {
                events.length = 0;
                press({code});
                press({code, repeat:true});
                assert.equal(events.length, 1);
                assert.equal(events[0].name, name);
                press({code, target:target('input')});
                assert.equal(events.length, 1);
            }
            events.length = 0;
            press({code:'KeyA'});
            assert.equal(events.at(-1).args.steering, -1);
            press({code:'ArrowRight'});
            heartbeat();
            assert.equal(events.at(-1).args.steering, -1);
        """)

    def run_javascript(self, scenario):
        script = HARNESS + "\neval(" + json.dumps(KEYBOARD_SCRIPT) + ");\n" + scenario
        result = subprocess.run([NODE, "-"], input=script, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_m_toggles_once_per_press_in_either_drive_mode_without_a_gimbal(self):
        self.run_javascript(r"""
            assert.equal(press().prevented, true);
            assert.equal(count(), 1);
            press({repeat:true});
            heartbeat();
            assert.equal(count(), 1);
            press();
            assert.equal(count(), 2);
            dataset.mode = 'dualshock';
            dataset.enabled = 'false';
            dataset.gimbal = 'false';
            press();
            assert.equal(count(), 3);
            // The expanded map is a nonmodal panel, so M can close it too.
            press({target:target('.map-expanded')});
            assert.equal(count(), 4);
            assert.ok(events.every(event => event.name === 'map_toggle'));
        """)

    def test_typing_dialogs_modifiers_and_focus_guard_the_map_shortcut(self):
        self.run_javascript(r"""
            for (const kind of ['input', 'textarea', 'select', '[role="slider"]',
                                '[contenteditable="true"]', '.q-dialog', '.q-menu', '.filter-controls']) {
                assert.equal(press({target:target(kind)}).prevented, undefined);
                document.activeElement = target(kind);
                press();
                document.activeElement = target();
            }
            for (const modifier of ['ctrlKey', 'altKey', 'metaKey']) press({[modifier]:true});
            focus = false; press(); focus = true;
            document.hidden = true; press(); document.hidden = false;
            dialog = true; press(); dialog = false;
            assert.equal(count(), 0);
            press();
            assert.equal(count(), 1);
            window.pingKeyboardCleanup();
            press();
            assert.equal(count(), 1);
        """)

    def test_expanded_map_releases_drive_and_gimbal_and_escape_closes_only_the_map(self):
        self.run_javascript(r"""
            assert.equal(press({code:'Escape'}).prevented, undefined);
            assert.equal(events.length, 0);
            press({code:'KeyW'});
            press({code:'KeyI'});
            dataset.mapOpen = 'true';
            heartbeat();
            assert.ok(events.some(event => event.name === 'virtual_drive' && event.args.release));
            assert.ok(events.some(event => event.name === 'camera_gimbal' && event.args.release));
            events.length = 0;
            press({code:'KeyW'});
            press({code:'KeyI'});
            assert.equal(events.length, 0);
            press();
            assert.equal(count(), 1);
            assert.equal(press({code:'Escape'}).prevented, true);
            press({code:'Escape', repeat:true});
            assert.equal(events.filter(event => event.name === 'map_close').length, 1);
            dialog = true;
            press({code:'Escape'});
            assert.equal(events.filter(event => event.name === 'map_close').length, 1);
        """)

    def test_space_activates_focused_map_without_driving_or_blocking_m(self):
        self.run_javascript(r"""
            press({code:'KeyW'});
            press({code:'KeyI'});
            events.length = 0;
            document.activeElement = target('.map-mini');
            const space = press({code:'Space', target:document.activeElement});
            assert.equal(space.prevented, undefined);
            assert.equal(space.stopped, undefined);
            assert.equal(events.length, 2);
            assert.ok(events.every(event => event.args.release === true));
            heartbeat();
            assert.equal(events.length, 2);
            press({target:document.activeElement});
            assert.equal(count(), 1);
        """)

    def test_space_on_map_zoom_buttons_does_not_drive_the_rover(self):
        self.run_javascript(r"""
            document.activeElement = target('.map-zoom-controls');
            const space = press({code:'Space', target:document.activeElement});
            assert.equal(space.prevented, undefined);
            assert.equal(events.length, 0);
            press({target:document.activeElement});
            assert.equal(count(), 1);
        """)


if __name__ == "__main__":
    unittest.main()
