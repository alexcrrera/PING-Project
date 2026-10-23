"""Browser keyboard bridge. Commands expire on the server if this bridge stops."""

KEYBOARD_SCRIPT = r"""
(() => {
    if (window.pingKeyboardCleanup) window.pingKeyboardCleanup();
    const keys = new Set();
    const codes = new Set(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space']);
    const abort = new AbortController();
    let held = false;
    const editable = target => target?.closest?.('input,textarea,select,[contenteditable="true"],.q-dialog,.q-menu');
    const enabled = () => {
        const guard = document.getElementById('virtual-drive-input');
        return guard?.dataset.mode === 'keyboard' && guard?.dataset.enabled === 'true'
            && !document.hidden && document.hasFocus()
            && !document.body.classList.contains('q-body--dialog') && !editable(document.activeElement);
    };
    const emit = payload => { if (typeof emitEvent === 'function') emitEvent('virtual_drive', payload); };
    const clear = () => {
        keys.clear();
        if (held) emit({release:true});
        held = false;
    };
    const send = () => {
        const has = (...names) => names.some(name => keys.has(name)) ? 1 : 0;
        emit({throttle:has('KeyW','ArrowUp')-has('KeyS','ArrowDown'),
              steering:has('KeyD','ArrowRight')-has('KeyA','ArrowLeft'), brake:keys.has('Space')});
        held = keys.size > 0;
    };
    document.addEventListener('keydown', event => {
        if (!codes.has(event.code)) return;
        if (!enabled() || event.ctrlKey || event.altKey || event.metaKey || editable(event.target)) { clear(); return; }
        event.preventDefault();
        event.stopPropagation();
        keys.add(event.code);
        send();
    }, {signal:abort.signal,capture:true});
    document.addEventListener('keyup', event => {
        if (!codes.has(event.code)) return;
        const wasHeld = keys.has(event.code);
        keys.delete(event.code);
        if (wasHeld) { event.preventDefault(); event.stopPropagation(); send(); }
    }, {signal:abort.signal,capture:true});
    window.addEventListener('blur', clear, {signal:abort.signal});
    document.addEventListener('visibilitychange', () => { if (document.hidden) clear(); }, {signal:abort.signal});
    document.addEventListener('focusin', event => { if (editable(event.target)) clear(); }, {signal:abort.signal});
    const heartbeat = setInterval(() => {
        if (!enabled()) clear();
        else if (keys.size) send();
    }, 100);
    window.pingKeyboardCleanup = () => { clear(); abort.abort(); clearInterval(heartbeat); };
    window.addEventListener('pagehide', window.pingKeyboardCleanup, {once:true,signal:abort.signal});
})();
"""
