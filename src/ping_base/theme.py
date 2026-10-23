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
.layout { display:grid; grid-template-columns:minmax(0,1fr) 284px; gap:16px; align-items:start; }
.visuals { min-width:0; display:flex; flex-direction:column; gap:12px; }
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
.camera-top { position:absolute; top:20px; left:22px; right:22px; display:flex; justify-content:space-between; align-items:flex-start; }
.camera-label { font-size:10px; letter-spacing:.12em; font-weight:500; display:flex; gap:8px; align-items:center; text-shadow:0 1px 3px #000; }
.signal-dot { width:5px; height:5px; border-radius:50%; display:inline-block; background:var(--accent); }
.camera-stamp { font-size:10px; letter-spacing:.08em; color:#dddcd0; text-shadow:0 1px 3px #000; }
.camera-compass { position:absolute; top:47px; left:50%; width:260px; transform:translateX(-50%); opacity:.75; }
.crosshair { position:absolute; width:64px; height:64px; top:50%; left:50%; transform:translate(-50%,-50%); opacity:.75; pointer-events:none; }
.camera-bottom { position:absolute; bottom:23px; left:23px; right:23px; display:flex; justify-content:space-between; align-items:flex-end; gap:12px; }
.camera-bottom .eyebrow { color:#c0c2b6; font-size:9px; }
.camera-readings { display:flex; gap:30px; }
.overlay-value { font-size:19px; margin-top:3px; font-variant-numeric:tabular-nums; }
.overlay-value small { font-size:11px; margin-left:4px; color:#c0c2b6; }
.camera-footer { height:24px; display:flex; align-items:center; justify-content:space-between; gap:8px; padding:0 14px; font-size:9px; letter-spacing:.05em; color:var(--muted); }
.camera-empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; background:#171916ee; color:var(--muted); font-size:13px; text-align:center; padding:25px; }
.camera-stage:fullscreen { height:100vh; width:100vw; }
.camera-stage:fullscreen .camera-image { object-fit:contain; }
.pose-body { display:grid; grid-template-columns:minmax(0,1fr) 160px; align-items:center; }
.rover-scene { width:100%!important; height:240px!important; }
.pose-values { border-left:1px solid var(--line); padding:0 22px; display:flex; flex-direction:column; gap:20px; }
.pose-number { font-size:23px; letter-spacing:-.03em; font-variant-numeric:tabular-nums; }
.pose-number small { font-size:12px; color:var(--muted); margin-left:5px; }
.pose-foot { font-size:9px; color:var(--dim); padding:0 14px 8px; display:flex; justify-content:space-between; gap:10px; }
.telemetry { background:transparent; }
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
@media(min-width:801px) and (min-height:660px) {
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
    .pose-body { min-height:0; grid-template-columns:minmax(0,1fr) 130px; }
    .rover-scene { min-height:0!important; height:100%!important; }
    .rover-scene canvas { display:block; }
    .pose-values { min-height:0; padding:0 18px; gap:clamp(5px,1.5vh,16px); }
    .pose-values .eyebrow { font-size:9px; }
    .pose-number { font-size:clamp(18px,2.4vh,23px); line-height:1.15; }
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
@media(min-width:1700px) { .layout { grid-template-columns:minmax(0,1fr) 310px; } .workspace { padding-left:28px; padding-right:28px; } }
@media(min-width:801px) and (max-height:850px) and (min-height:660px) {
    .workspace { padding-top:10px; padding-bottom:8px; grid-template-rows:38px minmax(0,1fr) 14px; row-gap:8px; }
    .intro h1 { font-size:21px; }
    .intro p { font-size:10px; }
    .visuals { gap:10px; grid-template-rows:minmax(0,2.3fr) minmax(0,1fr); }
    .visuals>.panel { grid-template-rows:30px minmax(0,1fr) 22px; }
    .panel-head { padding:0 12px; }
    .panel-title { font-size:10px; }
    .head-actions .q-btn { min-height:24px; padding:2px 5px; }
    .camera-top { top:14px; left:16px; right:16px; }
    .camera-compass { top:35px; width:220px; }
    .camera-bottom { bottom:14px; left:16px; right:16px; }
    .camera-readings { gap:24px; }
    .overlay-value { font-size:17px; }
    .pose-values { gap:5px; padding:0 14px; }
    .pose-values .eyebrow { font-size:8px; }
    .pose-number { font-size:18px; }
    .telemetry>.panel-head { height:30px; flex-basis:30px; }
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
@media(max-width:1100px) { .layout { grid-template-columns:minmax(0,1fr) 254px; gap:12px; } .workspace { padding-left:16px; padding-right:16px; } .shell { grid-template-columns:50px minmax(0,1fr); } .pose-values { padding:0 12px; } .pose-body { grid-template-columns:minmax(0,1fr) 110px; } .topbar { padding:0 18px; } .intro-right { gap:5px; } .intro-right .small-meta { font-size:9px; } }
@media(max-width:800px) { .layout { grid-template-columns:1fr; } .telemetry { display:grid; grid-template-columns:1fr 1fr; } .telemetry>.panel-head { grid-column:1/-1; } .telemetry-section { border-right:1px solid var(--line); } .shell { grid-template-columns:1fr; } .rail { display:none; } .topbar { padding:0 18px; height:64px; } .top-meta { gap:12px; } .session { display:none; } .brand { gap:12px; } .brand-word { font-size:21px; } .workspace { padding:22px 16px; } .intro { margin-bottom:20px; } .intro h1 { font-size:25px; } .intro-right .small-meta { display:none; } .camera-stage { height:45vw; min-height:280px; } .footer { flex-wrap:wrap; } }
@media(max-width:470px) { .telemetry { display:block; } .pose-body { grid-template-columns:minmax(0,1fr) 100px; } .pose-values { padding:0 10px; } .pose-number { font-size:20px; } .camera-readings { gap:17px; } .camera-compass { width:180px; } .camera-stamp { display:none; } .camera-bottom { left:16px; right:16px; } .brand .eyebrow { font-size:8px; } .top-meta { gap:4px; } .status-chip { font-size:8px; } }
"""
