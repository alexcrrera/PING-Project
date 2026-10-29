"""Restrained warm graphite, fine rules, and Suisse typography."""

CSS = r"""
:root { --bg:#111211; --panel:#191a18; --line:#343530; --text:#e8e7df;
        --muted:#999b91; --dim:#73766d; --accent:#d2d6b9; --warn:#d2ad76; }
html { scroll-behavior:smooth; }
body, .q-body--dark { background:var(--bg)!important; color:var(--text); }
body, .q-field, .q-btn, .q-tooltip, .q-dialog { font-family:Suisse,Helvetica,Arial,sans-serif!important; font-weight:300; }
body { font-size:14px; -webkit-font-smoothing:antialiased; }
.nicegui-content { padding:0!important; gap:0!important; }
h1,h2,h3,p { margin:0; }
button, a { -webkit-tap-highlight-color:transparent; }
button:focus-visible, a:focus-visible { outline:1px solid var(--accent)!important; outline-offset:4px; }
.q-btn { font-size:11px; font-weight:500; letter-spacing:.04em; border-radius:2px!important; }
.q-btn:before { box-shadow:none!important; }
.q-btn .q-focus-helper { opacity:0!important; }
.q-btn:hover { background:#ffffff08; }
.q-tooltip { font-size:12px; background:#343530; color:var(--text); }
.q-field--dark .q-field__control:before { border-color:var(--line); }
.topbar { width:100%; height:46px; padding:0 24px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.brand { display:flex; align-items:center; gap:18px; }
.brand-word { font-size:21px; font-weight:500; letter-spacing:.08em; }
.brand-divider { height:23px; width:1px; background:var(--line); }
.eyebrow { font-size:10px; font-weight:500; letter-spacing:.16em; line-height:1.6; text-transform:uppercase; color:var(--muted); }
.top-meta { display:flex; align-items:center; gap:24px; }
.session { color:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
.status-chip { font-size:10px; font-weight:500; letter-spacing:.08em; border:1px solid #4c5040; color:var(--accent); padding:4px 8px; border-radius:2px; }
.shell { display:grid; grid-template-columns:58px minmax(0,1fr); min-height:calc(100vh - 46px); width:100%; }
.rail { border-right:1px solid var(--line); display:flex; flex-direction:column; align-items:center; padding:18px 0 16px; gap:16px; }
.rail a { width:38px; height:38px; display:flex; align-items:center; justify-content:center; color:var(--dim); border-radius:3px; text-decoration:none; }
.rail a:hover { color:var(--text); background:#ffffff06; }
.rail a.active { color:var(--text); border:1px solid var(--line); background:#24251f; }
.rail .rail-settings { margin-top:auto; color:var(--muted); }
.workspace { padding:14px 24px 10px; min-width:0; }
.intro { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; gap:16px; }
.intro h1 { font-size:23px; font-weight:300; line-height:1.15; letter-spacing:-.035em; }
.intro p { color:var(--muted); margin-top:4px; font-size:11px; }
.intro-right { display:flex; gap:14px; align-items:center; }
.layout { --side-width:284px; display:grid; grid-template-columns:var(--side-width) minmax(0,1fr) var(--side-width); grid-template-areas:"controls visuals telemetry"; gap:16px; align-items:start; }
.visuals { grid-area:visuals; min-width:0; display:flex; flex-direction:column; gap:12px; }
.tools-sidebar { grid-area:controls; display:flex; flex-direction:column; min-height:0; background:transparent; }
.tools-sidebar>.panel-head { height:34px; flex:0 0 34px; padding:0 14px; }
.tools-scroll { flex:1; min-height:0; overflow:auto; scrollbar-width:thin; scrollbar-color:#73766d transparent; }
.navigation-panel { flex:0 0 auto; padding:9px 10px 8px; border-top:1px solid var(--line); background:#151813; }
.navigation-head { display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px; }
.navigation-head .eyebrow { color:#c7ccb5; font-size:9px; }
.navigation-head .q-btn { min-height:24px; padding:2px 5px; color:var(--text); font-size:9px; }
.map-mini { display:block; width:100%; max-width:300px; aspect-ratio:1; margin:0 auto; border:1px solid #6b74514d; background:#10150f; overflow:hidden; cursor:zoom-in; }
.map-mini:focus-visible { outline:1px solid #d2d6b9; outline-offset:3px; }
.map-viewport { position:relative; margin:0 auto; }
.map-mini-viewport { width:100%; max-width:300px; }
.map-zoom-controls { position:absolute; top:8px; left:8px; z-index:2; display:flex; align-items:center; background:#10170ff0; border:1px solid #88947499; box-shadow:0 2px 8px #0005; }
.map-zoom-controls .q-btn { min-width:26px; min-height:26px; padding:3px 5px; color:#edf0df; font-size:10px; }
.map-zoom-controls .q-btn .q-icon { font-size:16px; }
.map-zoom-controls .q-btn+.q-btn { border-left:1px solid #59634c; }
.map-mini>svg, .map-large>svg { display:block; width:100%; height:100%; }
.navigation-coordinates { color:#eceee0; font-size:10px; font-variant-numeric:tabular-nums; line-height:1.5; margin-top:6px; white-space:nowrap; }
.navigation-state { color:#a9b096; font-size:8px; line-height:1.4; letter-spacing:.07em; }
.map-overlay { position:fixed; inset:0; z-index:8000; display:flex; align-items:center; justify-content:center; padding:16px; background:#080c0bea; backdrop-filter:blur(5px); overflow:auto; }
.map-overlay.hidden, .map-overlay[hidden] { display:none!important; }
.map-expanded-card { width:min(860px,94vw); max-height:calc(100dvh - 32px); padding:14px; border:1px solid #6b7451; border-radius:2px; background:#151a14; box-shadow:0 20px 80px #0009; overflow:auto; }
.map-expanded-head { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-bottom:12px; border-bottom:1px solid #414a37; padding-bottom:9px; }
.map-expanded-head .eyebrow { color:#e2e7d1; }
.map-expanded-head .q-btn { color:#e2e7d1; min-height:28px; }
.map-large-viewport { width:min(75vw,calc(100dvh - 190px),720px); }
.map-large { display:block; width:100%; aspect-ratio:1; margin:0 auto; background:#10150f; border:1px solid #66734e80; }
.map-expanded-footer { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:5px 14px; margin-top:10px; color:#b9c0aa; font-size:10px; font-variant-numeric:tabular-nums; }
.tool-section { padding:12px; border-bottom:1px solid var(--line); }
.tool-section:last-child { border-bottom:0; }
.stabilization-toggle { margin:8px 0; width:100%; }
.camera-indicators { display:flex; gap:8px; align-items:center; }
.stabilization-marker { min-height:22px; padding:2px 6px; font-size:9px; letter-spacing:.05em; border:1px solid var(--line); background:#171916bb; }
.stabilization-off { color:var(--muted)!important; }
.stabilization-on { color:var(--accent)!important; border-color:#8c9872!important; background:#59634630!important; }
.filter-controls { display:flex; flex-direction:column; gap:9px; }
.filter-summary { font-size:10px; line-height:1.5; color:var(--muted); overflow-wrap:anywhere; }
.panel { border:1px solid var(--line); background:var(--panel); border-radius:3px; overflow:hidden; min-width:0; }
.panel-head { min-height:34px; padding:0 14px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); }
.panel-title { display:flex; gap:10px; align-items:center; font-size:11px; font-weight:500; letter-spacing:.06em; }
.section-index { font-size:10px; color:var(--dim); margin-right:4px; }
.head-actions { display:flex; align-items:center; gap:6px; }
.head-actions .q-btn { min-height:28px; padding:3px 7px; color:var(--muted); }
.small-meta { color:var(--muted); font-size:10px; letter-spacing:.07em; font-weight:500; }
.camera-stage { height:clamp(290px,42vh,600px); min-height:290px; position:relative; overflow:hidden; background:#171916; }
.camera-image { width:100%; height:100%; object-fit:cover; display:block; }
.camera-vignette { position:absolute; inset:0; pointer-events:none; box-shadow:inset 0 0 120px #0005; background:linear-gradient(0deg,#000a,transparent 26%,transparent 80%,#0005); }
.camera-top { position:absolute; top:16px; left:18px; right:18px; display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.camera-label { font-size:9px; letter-spacing:.1em; font-weight:500; display:flex; gap:7px; align-items:center; padding:5px 7px; color:#f0f3e3; background:#10170dcf; border:1px solid #c2c9a44d; text-shadow:0 1px 2px #000; white-space:nowrap; }
.signal-dot { width:5px; height:5px; border-radius:50%; display:inline-block; background:var(--accent); }
.camera-stamp { font-size:10px; letter-spacing:.06em; color:#f0f3e3; text-shadow:0 1px 2px #000; font-variant-numeric:tabular-nums; }
.camera-indicators { padding:3px 6px; gap:7px; background:#10170dcf; border:1px solid #c2c9a44d; white-space:nowrap; }
.camera-indicators .stabilization-marker { border-color:#c2c9a466; color:#edf0dd!important; background:#273020d9!important; font-weight:500; }
.filter-panel-heading { display:flex; align-items:center; justify-content:space-between; position:sticky; top:0; background:var(--bg); z-index:3; flex-shrink:0; padding:3px 0; }
.filter-panel-heading .q-btn { min-height:20px; padding:0 2px; color:var(--muted); }
.filter-panel-actions { display:flex; align-items:center; gap:5px; }
.filter-panel-heading .filter-panel-actions .q-btn { font-size:10px; padding:1px 3px; }
.filter-switch-grid { display:grid; grid-template-columns:1fr 1fr; gap:7px 9px; }
.filter-switch-grid .q-checkbox { align-items:flex-start; line-height:1.3; }
.filter-group-title { font-size:9px; letter-spacing:.1em; color:var(--muted); margin-top:4px; }
.filter-note { font-size:9px; line-height:1.4; color:var(--muted); border-top:1px solid var(--line); padding-top:7px; }
.camera-style-note { position:absolute; top:46px; left:18px; font-size:9px; color:var(--warn); letter-spacing:.07em; text-shadow:0 1px 3px #000; pointer-events:none; }
.filter-control-label { font-size:10px; color:var(--muted); margin-bottom:9px; }
.edge-filter-controls .q-slider { margin:2px 0 4px; }
.filter-controls .q-checkbox { font-size:11px; min-height:21px; }
.artificial-horizon { position:absolute; top:50%; left:50%; width:280px; height:168px; transform:translate(-50%,-50%); pointer-events:none; overflow:hidden; }
.artificial-horizon svg { width:100%; height:100%; }
.artificial-horizon text { font-family:Suisse,Arial,sans-serif; font-size:9px; fill:#e5eacb; stroke:none; }
.gimbal-tools { position:absolute; top:118px; right:18px; display:flex; flex-direction:column; align-items:flex-end; gap:4px; }
.gimbal-buttons { display:flex; gap:1px; background:#10170de8; border:1px solid #c2c9a459; border-radius:2px; }
.gimbal-buttons .q-btn { min-height:25px; padding:2px 4px; color:#f0f3e3; }
.gimbal-buttons .q-icon { font-size:18px; }
.gimbal-readout { font-size:9px; letter-spacing:.04em; color:#edf0df; padding:3px 5px; background:#10170dcf; border:1px solid #c2c9a433; text-shadow:0 1px 2px #000; font-variant-numeric:tabular-nums; }
.camera-compass { position:absolute; top:54px; left:50%; width:280px; max-width:calc(100% - 32px); height:56px; transform:translateX(-50%); pointer-events:none; filter:drop-shadow(0 2px 3px #0008); }
.camera-compass svg { width:100%; height:100%; display:block; }
.crosshair { position:absolute; width:110px; height:83px; top:50%; left:50%; transform:translate(-50%,-50%); opacity:1; pointer-events:none; filter:drop-shadow(0 1px 2px #0007); }
.crosshair svg { width:100%; height:100%; display:block; }
.rangefinder-overlay { position:absolute; top:calc(50% + 51px); left:50%; transform:translateX(-50%); display:flex; align-items:center; gap:8px; padding:4px 7px; color:#f3f6e6; background:#0d140bdf; border:1px solid #c2c9a45e; pointer-events:none; text-shadow:0 1px 2px #000; white-space:nowrap; }
.rangefinder-label { color:#c9cdb4; font-size:7px; letter-spacing:.09em; }
.rangefinder-value { font-size:14px; font-weight:500; line-height:1.15; font-variant-numeric:tabular-nums; }
.camera-bottom { position:absolute; bottom:18px; left:18px; right:18px; display:flex; justify-content:space-between; align-items:flex-end; gap:12px; }
.camera-bottom .eyebrow { color:#dbe2c7; font-size:8px; letter-spacing:.1em; }
.camera-telemetry { display:flex; flex-direction:column; gap:7px; min-width:0; padding:7px 9px; background:#0d140bcf; border:1px solid #c2c9a447; box-shadow:0 2px 10px #0003; }
.camera-gps { color:#edf2dc; font-size:9px; line-height:1.2; letter-spacing:.025em; font-variant-numeric:tabular-nums; text-shadow:0 1px 2px #000; white-space:nowrap; }
.camera-bottom>.eyebrow { padding:4px 6px; background:#0d140bcf; border:1px solid #c2c9a43d; color:#e1e7ce; white-space:nowrap; }
.camera-readings { display:flex; gap:30px; }
.overlay-value { font-size:19px; margin-top:3px; font-weight:500; color:#f3f6e6; line-height:1.15; text-shadow:0 1px 3px #000; font-variant-numeric:tabular-nums; }
.overlay-value small { font-size:11px; margin-left:4px; color:#c0c2b6; }
.camera-footer { height:24px; display:flex; align-items:center; justify-content:space-between; gap:8px; padding:0 14px; font-size:9px; letter-spacing:.05em; color:var(--muted); }
.camera-empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; background:#171916ee; color:var(--muted); font-size:13px; text-align:center; padding:25px; }
.camera-stage:fullscreen { height:100vh; width:100vw; }
.camera-stage:fullscreen .camera-image { object-fit:contain; }
.pose-body { display:grid; grid-template-columns:minmax(0,1fr) minmax(280px,46%); align-items:stretch; }
.rover-scene { width:100%!important; height:240px!important; }
.orientation-dials { border-left:1px solid var(--line); min-width:0; min-height:0; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); grid-template-rows:minmax(0,1fr) auto; gap:5px 8px; padding:12px; align-content:center; }
.orientation-dial { min-width:0; min-height:0; display:flex; flex-direction:column; align-items:center; text-align:center; }
.orientation-dial>.eyebrow { font-size:9px; letter-spacing:.12em; }
.orientation-svg { width:100%; max-width:120px; flex:1; min-height:0; max-height:132px; display:flex; align-items:center; }
.orientation-svg svg { display:block; width:100%; height:100%; }
.orientation-value { font-size:16px; line-height:1.25; font-variant-numeric:tabular-nums; white-space:nowrap; }
.orientation-caption, .orientation-camera { font-size:8px; letter-spacing:.04em; line-height:1.5; white-space:nowrap; }
.orientation-caption { color:var(--dim); }
.orientation-camera { color:#c5a35c; font-variant-numeric:tabular-nums; }
.orientation-legend { grid-column:1/-1; display:flex; justify-content:center; flex-wrap:wrap; gap:3px 12px; font-size:8px; line-height:1.3; letter-spacing:.05em; }
.orientation-rover-key { color:var(--muted); }
.pose-foot { font-size:9px; color:var(--dim); padding:0 14px 8px; display:flex; justify-content:space-between; gap:10px; }
.telemetry { grid-area:telemetry; background:transparent; }
.telemetry .panel-head { padding:0 17px; }
.telemetry-section { padding:16px 20px 14px; border-bottom:1px solid var(--line); }
.speed-header { display:flex; justify-content:space-between; align-items:center; }
.speed-value { font-size:48px; line-height:1; margin-top:12px; letter-spacing:-.065em; font-variant-numeric:tabular-nums; }
.speed-unit { font-size:13px; color:var(--muted); letter-spacing:0; margin-left:8px; }
.sparkline { height:34px; margin:10px 0 7px; width:100%; display:block; }
.graph-foot { display:flex; justify-content:space-between; font-size:9px; color:var(--dim); letter-spacing:.05em; }
.metric-row { display:flex; align-items:center; justify-content:space-between; gap:6px; padding:6px 0; font-size:12px; line-height:1.3; }
.metric-row .value { font-size:16px; font-variant-numeric:tabular-nums; }
.metric-row .unit { font-size:10px; color:var(--muted); margin-left:4px; }
.metric-name { color:var(--muted); }
.battery-bar { height:3px; width:100%; background:#32352b; margin:4px 0 10px; }
.battery-fill { height:100%; background:var(--accent); transition:width .3s; }
.traction-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.wheel-row { display:grid; grid-template-columns:27px 1fr 44px; align-items:center; gap:10px; margin-top:8px; }
.wheel-label { color:var(--muted); font-size:10px; }
.wheel-track { height:4px; background:#30322c; width:100%; }
.wheel-fill { background:#bdc2a5; height:100%; transition:width .2s; }
.wheel-value { font-size:11px; text-align:right; font-variant-numeric:tabular-nums; }
.subtext { color:var(--dim); font-size:10px; line-height:1.6; }
.controller-row { display:flex; justify-content:space-between; align-items:center; gap:8px; font-size:12px; margin:10px 0; }
.controller-state { font-size:10px; font-weight:500; letter-spacing:.08em; color:var(--muted); }
.controller-axes { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:13px; }
.axis-readout { font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums; }
.footer { display:flex; justify-content:space-between; gap:12px; align-items:center; font-size:9px; color:var(--dim); margin-top:8px; line-height:1.6; }
.footer-status { display:flex; align-items:center; gap:8px; }
.settings-card { width:480px; max-width:94vw!important; background:#1a1b18!important; border:1px solid var(--line); padding:28px!important; gap:18px!important; border-radius:3px!important; }
.settings-card h2 { font-size:23px; font-weight:300; }
.settings-card .q-field { width:100%; }
.settings-card .q-btn { color:var(--text); }
.dialog-note { color:var(--muted); font-size:12px; line-height:1.65; }
.dialog-actions { width:100%; display:flex; justify-content:flex-end; gap:8px; }
.q-notification { background:#35372f!important; color:var(--text)!important; }
/* Desktop is a single instrument panel: the camera and model share the
   available height instead of stacking their independent fixed heights. */
@media(min-width:1101px) and (min-height:660px) {
    html, body, #q-app { height:100%; }
    .nicegui-content { height:100dvh; min-height:0; display:flex; flex-direction:column; }
    .topbar { height:46px; min-height:46px; }
    .brand .eyebrow { font-size:9px; line-height:1.4; }
    .shell { flex:1; height:calc(100dvh - 46px); min-height:0; }
    .rail { min-height:0; }
    .workspace { min-height:0; display:grid; grid-template-rows:42px minmax(0,1fr) 15px; row-gap:10px; }
    .intro { margin:0; min-height:0; }
    .intro p { margin-top:3px; }
    .intro-right { gap:10px; }
    .intro-right .q-btn { font-size:10px; }
    .layout { min-height:0; height:100%; align-items:stretch; }
    .visuals { min-height:0; height:100%; display:grid; grid-template-rows:minmax(0,2.15fr) minmax(0,1fr); }
    .visuals>.panel { min-height:0; display:grid; grid-template-rows:34px minmax(0,1fr) 24px; }
    .panel-head { min-height:0; }
    .camera-stage { height:100%; min-height:0; }
    .camera-footer { height:auto; }
    .pose-body { min-height:0; }
    .rover-scene { min-height:0!important; height:100%!important; }
    .rover-scene canvas { display:block; }
    .orientation-dials { padding:7px 10px; gap:3px 6px; }
    .pose-foot { align-items:center; padding-bottom:0; }
    .telemetry { min-height:0; display:flex; flex-direction:column; }
    .telemetry>.panel-head { height:34px; flex:0 0 34px; padding:0 14px; }
    .telemetry-section { padding:clamp(6px,.9vh,12px) 16px; flex:1 0 auto; }
    .telemetry-section .eyebrow { font-size:9px; line-height:1.4; }
    .telemetry-section .metric-row { padding:4px 0; font-size:11px; }
    .telemetry-section .metric-row .value { font-size:14px; }
    .telemetry-section .metric-row .unit { font-size:9px; }
    .telemetry-section .subtext { font-size:9px; line-height:1.4; }
    .telemetry-section .subtext.mt-3 { margin-top:5px!important; }
    .telemetry-section .subtext.mt-2 { margin-top:4px!important; }
    .telemetry-section:nth-child(2) { display:grid; grid-template-columns:90px minmax(0,1fr); column-gap:12px; align-items:center; }
    .telemetry-section:nth-child(2) .speed-header, .telemetry-section:nth-child(2) .graph-foot { grid-column:1/-1; }
    .speed-value { font-size:42px; margin-top:5px; }
    .sparkline { height:30px; margin:6px 0; }
    .graph-foot { margin-top:5px; font-size:8px; }
    .battery-bar { margin:2px 0 4px; }
    .telemetry-section:nth-child(4) { display:grid; grid-template-columns:1fr 1fr; column-gap:14px; }
    .telemetry-section:nth-child(4) .traction-head, .telemetry-section:nth-child(4)>.subtext { grid-column:1/-1; }
    .traction-head { margin-bottom:4px; }
    .wheel-row { grid-template-columns:18px minmax(0,1fr) 34px; gap:5px; margin-top:5px; }
    .wheel-label { font-size:9px; }
    .wheel-value { font-size:10px; }
    .telemetry-section:nth-child(5) { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); column-gap:8px; }
    .telemetry-section:nth-child(5)>.eyebrow, .telemetry-section:nth-child(5)>.subtext { grid-column:1/-1; }
    .telemetry-section:nth-child(5) .metric-row { flex-direction:column; align-items:flex-start; gap:2px; padding-top:6px; }
    .controller-row { font-size:10px; margin:7px 0 5px; }
    .controller-state { font-size:9px; }
    .controller-axes { gap:8px; margin-top:5px; }
    .axis-readout { font-size:10px; }
    .drive-controls { margin-top:5px; }
    .drive-mode { display:flex; margin-top:6px; width:100%; }
    .drive-mode .q-btn { min-height:26px; flex:1; padding:3px 8px; font-size:10px; }
    .drive-mode .q-btn--active { background:#d2d6b91a!important; color:var(--accent)!important; }
    .drive-mode .q-btn[aria-pressed="true"] { color:#171916!important; font-weight:500; }
    .control-hint { font-size:10px; color:var(--muted); line-height:1.4; margin-top:5px; font-variant-numeric:tabular-nums; }
    .footer { margin:0; min-width:0; white-space:nowrap; }
    .footer-status { min-width:0; }
    .footer-status>.nicegui-label { overflow:hidden; text-overflow:ellipsis; }
}
@media(min-width:1700px) { .layout { --side-width:310px; } .workspace { padding-left:28px; padding-right:28px; } }
@media(min-width:1101px) and (max-height:850px) and (min-height:660px) {
    .workspace { padding-top:10px; padding-bottom:8px; grid-template-rows:38px minmax(0,1fr) 14px; row-gap:8px; }
    .intro h1 { font-size:21px; }
    .intro p { font-size:10px; }
    .visuals { gap:10px; grid-template-rows:minmax(0,2.3fr) minmax(0,1fr); }
    .visuals>.panel { grid-template-rows:30px minmax(0,1fr) 22px; }
    .panel-head { padding:0 12px; }
    .panel-title { font-size:10px; }
    .head-actions .q-btn { min-height:24px; padding:2px 5px; }
    .camera-top { top:12px; left:14px; right:14px; }
    .camera-compass { top:47px; width:260px; height:52px; }
    .gimbal-tools { top:106px; right:14px; }
    .camera-bottom { bottom:14px; left:16px; right:16px; }
    .camera-readings { gap:24px; }
    .overlay-value { font-size:17px; }
    .pose-body { grid-template-columns:minmax(0,1fr) minmax(255px,46%); }
    .orientation-dials { padding:5px 8px; gap:2px 4px; }
    .orientation-dial>.eyebrow { font-size:8px; }
    .orientation-value { font-size:14px; }
    .orientation-caption, .orientation-camera, .orientation-legend { font-size:7px; }
    .telemetry>.panel-head, .tools-sidebar>.panel-head { height:30px; flex-basis:30px; }
    .telemetry-section { padding:6px 14px; }
    .telemetry-section .metric-row { padding:3px 0; font-size:10px; }
    .telemetry-section .metric-row .value { font-size:13px; }
    .telemetry-section .metric-row .unit { font-size:8px; }
    .telemetry-section .subtext { font-size:8px; }
    .telemetry-section:nth-child(2) { grid-template-columns:79px minmax(0,1fr); }
    .speed-value { font-size:36px; margin-top:3px; }
    .sparkline { height:25px; margin:4px 0; }
    .graph-foot { margin-top:3px; }
    .wheel-row { margin-top:4px; }
    .telemetry-section:nth-child(5) .metric-row { padding-top:4px; }
    .controller-row { margin:5px 0 3px; }
    .controller-axes { margin-top:3px; }
    .drive-mode { margin-top:4px; }
    .drive-mode .q-btn { min-height:24px; }
    .control-hint { margin-top:3px; font-size:9px; }
}
@media(max-width:1100px) { .layout { grid-template-columns:minmax(0,1fr); grid-template-areas:"visuals" "controls" "telemetry"; gap:12px; } .workspace { padding-left:16px; padding-right:16px; } .shell { grid-template-columns:50px minmax(0,1fr); } .topbar { padding:0 18px; } .intro-right { gap:5px; } .intro-right .small-meta { font-size:9px; } .tools-scroll { overflow:visible; } .tools-sidebar .filter-switch-grid { grid-template-columns:1fr 1fr; } .telemetry { display:grid; grid-template-columns:1fr 1fr; } .telemetry>.panel-head { grid-column:1/-1; } }
@media(max-width:800px) { .layout { grid-template-columns:1fr; } .telemetry { display:grid; grid-template-columns:1fr 1fr; } .telemetry>.panel-head { grid-column:1/-1; } .telemetry-section { border-right:1px solid var(--line); } .shell { grid-template-columns:1fr; } .rail { display:none; } .topbar { padding:0 18px; height:64px; } .top-meta { gap:12px; } .session { display:none; } .brand { gap:12px; } .brand-word { font-size:21px; } .workspace { padding:22px 16px; } .intro { margin-bottom:20px; } .intro h1 { font-size:25px; } .intro-right .small-meta { display:none; } .camera-stage { height:45vw; min-height:280px; } .footer { flex-wrap:wrap; } }
@media(max-width:600px) { .pose-body { grid-template-columns:minmax(0,1fr); } .rover-scene { height:210px!important; } .orientation-dials { border-left:0; border-top:1px solid var(--line); min-height:172px; padding:10px 14px; } .orientation-svg { height:105px; flex:none; } }
@media(max-width:470px) { .rangefinder-overlay { top:calc(50% + 43px); padding:3px 5px; gap:6px; } .rangefinder-value { font-size:12px; } }
@media(max-width:470px) { .telemetry { display:block; } .camera-readings { gap:17px; } .camera-top { left:10px; right:10px; gap:6px; } .camera-label { padding:4px 5px; font-size:8px; letter-spacing:.06em; gap:5px; } .camera-indicators { padding:2px 3px; } .camera-compass { width:250px; top:48px; height:50px; } .camera-stamp { display:none; } .gimbal-tools { top:104px; right:10px; } .camera-bottom { left:10px; right:10px; bottom:10px; gap:6px; } .camera-telemetry { padding:6px; gap:5px; } .camera-gps { font-size:8px; letter-spacing:0; } .camera-bottom .eyebrow { font-size:7px; } .camera-bottom>.eyebrow { padding:3px; font-size:7px; } .overlay-value { font-size:16px; } .crosshair { width:96px; height:72px; } .map-overlay { padding:8px; } .map-expanded-card { width:96vw; padding:10px; max-height:calc(100dvh - 16px); } .map-expanded-head { gap:6px; } .map-expanded-head .eyebrow { font-size:9px; } .map-large-viewport { width:min(88vw,calc(100dvh - 190px),720px); } .map-expanded-footer { font-size:9px; gap:5px; } .brand .eyebrow { font-size:8px; } .top-meta { gap:4px; } .status-chip { font-size:8px; } }
"""
