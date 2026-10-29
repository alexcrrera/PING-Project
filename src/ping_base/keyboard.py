"""Dashboard shortcuts and driving bridge. Drive commands expire on the server."""

KEYBOARD_SCRIPT = r"""
(() => {
    if (window.pingKeyboardCleanup) window.pingKeyboardCleanup();
    const keys = new Set();
    const codes = new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space']);
    const gimbalKeys = new Set();
    const gimbalCodes = new Set(['KeyI','KeyJ','KeyK','KeyL']);
    const abort = new AbortController();
    let held = false;
    let gimbalHeld = false;
    const editable = target => target?.closest?.('input,textarea,select,[role="slider"],[contenteditable="true"],.q-dialog,.q-menu,.filter-controls');
    const shortcutsEnabled = () => !document.hidden && document.hasFocus()
        && !document.body.classList.contains('q-body--dialog') && !editable(document.activeElement);
    const mapOpen = () => document.getElementById('virtual-drive-input')?.dataset.mapOpen === 'true';
    const gimbalEnabled = () => shortcutsEnabled()
        && !mapOpen() && document.getElementById('virtual-drive-input')?.dataset.gimbal === 'true';
    const enabled = () => {
        const guard = document.getElementById('virtual-drive-input');
        return guard?.dataset.mode === 'keyboard' && guard?.dataset.enabled === 'true'
            && !mapOpen() && shortcutsEnabled();
    };
    const emit = payload => { if (typeof emitEvent === 'function') emitEvent('virtual_drive', payload); };
    const emitCamera = (name, payload = {}) => { if (typeof emitEvent === 'function') emitEvent(name, payload); };
    const clearGimbal = () => {
        gimbalKeys.clear();
        if (gimbalHeld) emitCamera('camera_gimbal', {release:true});
        gimbalHeld = false;
    };
    const clear = () => {
        keys.clear();
        if (held) emit({release:true});
        held = false;
        clearGimbal();
    };
    const send = () => {
        const has = (...names) => names.some(name => keys.has(name)) ? 1 : 0;
        emit({throttle:has('KeyW','ArrowUp')-has('KeyS','ArrowDown'),
              steering:has('KeyD','ArrowRight')-has('KeyA','ArrowLeft'), brake:keys.has('Space')});
        held = keys.size > 0;
    };
    const sendGimbal = () => {
        const has = name => gimbalKeys.has(name) ? 1 : 0;
        emitCamera('camera_gimbal', {yaw:has('KeyL')-has('KeyJ'), pitch:has('KeyI')-has('KeyK')});
        gimbalHeld = gimbalKeys.size > 0;
    };
    document.addEventListener('keydown', event => {
        if (event.code === 'Escape' && mapOpen()) {
            if (!shortcutsEnabled() || event.ctrlKey || event.altKey || event.metaKey || editable(event.target)) return;
            event.preventDefault();
            event.stopPropagation();
            if (!event.repeat) emitCamera('map_close');
            return;
        }
        if (event.code === 'KeyQ' || event.code === 'KeyM' || event.code === 'KeyR' || event.code === 'KeyZ' || gimbalCodes.has(event.code)) {
            if (!shortcutsEnabled() || event.ctrlKey || event.altKey || event.metaKey || editable(event.target)) return;
            if (event.code !== 'KeyQ' && event.code !== 'KeyM' && !gimbalEnabled()) return;
            event.preventDefault();
            event.stopPropagation();
            if (event.repeat) return;
            if (event.code === 'KeyQ') emitCamera('camera_zoom');
            else if (event.code === 'KeyM') emitCamera('map_toggle');
            else if (event.code === 'KeyR') { clearGimbal(); emitCamera('camera_home'); }
            else if (event.code === 'KeyZ') emitCamera('camera_stabilization');
            else { gimbalKeys.add(event.code); sendGimbal(); }
            return;
        }
        if (event.code === 'Space' && event.target?.closest?.('.map-mini, .map-zoom-controls')) { clear(); return; }
        if (!codes.has(event.code)) return;
        if (!enabled() || event.ctrlKey || event.altKey || event.metaKey || editable(event.target)) { clear(); return; }
        event.preventDefault();
        event.stopPropagation();
        keys.add(event.code);
        send();
    }, {signal:abort.signal,capture:true});
    document.addEventListener('keyup', event => {
        if (gimbalCodes.has(event.code)) {
            const wasHeld = gimbalKeys.delete(event.code);
            if (wasHeld) { event.preventDefault(); event.stopPropagation(); sendGimbal(); }
            return;
        }
        if (!codes.has(event.code)) return;
        const wasHeld = keys.has(event.code);
        keys.delete(event.code);
        if (wasHeld) { event.preventDefault(); event.stopPropagation(); send(); }
    }, {signal:abort.signal,capture:true});
    window.addEventListener('blur', clear, {signal:abort.signal});
    document.addEventListener('visibilitychange', () => { if (document.hidden) clear(); }, {signal:abort.signal});
    document.addEventListener('focusin', event => { if (editable(event.target)) clear(); }, {signal:abort.signal});
    const heartbeat = setInterval(() => {
        if (!shortcutsEnabled()) { clear(); return; }
        if (!enabled()) {
            keys.clear();
            if (held) emit({release:true});
            held = false;
        }
        else if (keys.size) send();
        if (!gimbalEnabled()) clearGimbal();
        else if (gimbalKeys.size) sendGimbal();
    }, 100);
    window.pingKeyboardCleanup = () => { clear(); abort.abort(); clearInterval(heartbeat); };
    window.addEventListener('pagehide', window.pingKeyboardCleanup, {once:true,signal:abort.signal});
})();
"""
