"""Browser keyboard bridge for the digital twin's driving controls."""

KEYBOARD_SCRIPT = r"""
(() => {
    if (window.pingTwinKeyboardCleanup) window.pingTwinKeyboardCleanup();
    const keys = new Set();
    const driveCodes = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD',
                                'ArrowUp', 'ArrowLeft', 'ArrowDown', 'ArrowRight']);
    const abort = new AbortController();
    const editable = target => target?.closest?.('input, textarea, select, [contenteditable="true"], [role="slider"], .q-field, .q-menu');
    const available = () => !document.hidden && document.hasFocus() && !editable(document.activeElement);
    const emit = payload => { if (typeof emitEvent === 'function') emitEvent('twin_keyboard', payload); };
    const send = () => {
        const has = (...names) => names.some(name => keys.has(name));
        emit({throttle: Number(has('KeyW', 'ArrowUp')) - Number(has('KeyS', 'ArrowDown')),
              steer: Number(has('KeyD', 'ArrowRight')) - Number(has('KeyA', 'ArrowLeft')),
              throttle_active: has('KeyW', 'ArrowUp', 'KeyS', 'ArrowDown'),
              steer_active: has('KeyA', 'ArrowLeft', 'KeyD', 'ArrowRight')});
    };
    const clear = () => { if (keys.size) { keys.clear(); emit({release: true}); } };
    document.addEventListener('keydown', event => {
        if (!driveCodes.has(event.code)) return;
        if (!available() || event.ctrlKey || event.altKey || event.metaKey || editable(event.target)) { clear(); return; }
        event.preventDefault();
        event.stopPropagation();
        keys.add(event.code);
        send();
    }, {signal: abort.signal, capture: true});
    document.addEventListener('keyup', event => {
        if (!driveCodes.has(event.code) || !keys.delete(event.code)) return;
        event.preventDefault();
        event.stopPropagation();
        if (keys.size) send(); else emit({release: true});
    }, {signal: abort.signal, capture: true});
    window.addEventListener('blur', clear, {signal: abort.signal});
    window.addEventListener('pagehide', clear, {signal: abort.signal});
    document.addEventListener('visibilitychange', () => { if (document.hidden) clear(); }, {signal: abort.signal});
    document.addEventListener('focusin', event => { if (editable(event.target)) clear(); }, {signal: abort.signal});
    const heartbeat = setInterval(() => {
        if (!available()) clear();
        else if (keys.size) send();
    }, 100);
    window.pingTwinKeyboardCleanup = () => { clear(); abort.abort(); clearInterval(heartbeat); };
})();
"""
