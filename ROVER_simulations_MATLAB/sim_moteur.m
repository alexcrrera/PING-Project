function out = sim_moteur(P, T, opt)
% SIM_MOTEUR  Simulation d'UN moteur avec sa boucle interne (courant + vitesse).
% Plante continue intégrée à dt = 10 us, PI discrets à leur vraie fréquence,
% retard d'un échantillon sur chaque boucle, saturations, anti-windup.
%
% opt (champs optionnels) :
%   mode    'cascade' (défaut) ou 'current' (boucle courant seule)
%   wref    @(t) consigne de vitesse (rad/s)       [cascade]
%   iref    @(t) consigne de courant (A)           [current]
%   Cr      @(t) couple de charge (N.m)            défaut 0
%   J, L    inertie et inductance de la plante     défaut P.J_nom, P.L
%   blocked true = rotor bloqué
%   mesure  'ideale' (défaut), 'comptage' ou 'periode'

if ~isfield(opt,'mode'),    opt.mode = 'cascade'; end
if ~isfield(opt,'wref'),    opt.wref = @(t) 0; end
if ~isfield(opt,'iref'),    opt.iref = @(t) 0; end
if ~isfield(opt,'Cr'),      opt.Cr = @(t) 0; end
if ~isfield(opt,'J'),       opt.J = P.J_nom; end
if ~isfield(opt,'L'),       opt.L = P.L; end
if ~isfield(opt,'blocked'), opt.blocked = false; end
if ~isfield(opt,'mesure'),  opt.mesure = 'ideale'; end
cascade = strcmp(opt.mode,'cascade');

dt = 1e-5;  n = round(T/dt);
ki = round(P.Ts_i/dt);  kw = round(P.Ts_w/dt);
pi_i = pi_init(P.Kp_i, P.Ki_i, P.Ts_i, -P.U_bat, P.U_bat);
pi_w = pi_init(P.Kp_w, P.Ki_w, P.Ts_w, -P.I_max, P.I_max);

i = 0; w = 0; th = 0;
V = 0; Vnext = 0; Iref = 0; Inext = 0;
th_prev = 0; w_meas = 0; last_cnt = 0; edge = [0 0];
q = 2*pi/P.CPR;

dec = 10; nl = floor(n/dec);
out.t = zeros(nl,1); out.i = out.t; out.w = out.t; out.V = out.t;
out.Iref = out.t; out.wref = out.t; out.wmeas = out.t;
l = 0;
for k = 0:n-1
    t = k*dt;
    % ---- boucle vitesse (500 Hz)
    if cascade && mod(k,kw) == 0
        switch opt.mesure
            case 'comptage'
                w_meas = (floor(th/q) - floor(th_prev/q))*q/P.Ts_w;
            case 'periode'
                if edge(2) > edge(1) && edge(1) > 0 && (t - edge(2)) < 0.02
                    w_meas = q/(edge(2) - edge(1));
                else
                    w_meas = 0;
                end
            otherwise
                w_meas = w;
        end
        th_prev = th;
        Iref = Inext;                                  % retard d'un échantillon
        [Inext, pi_w] = pi_step(pi_w, opt.wref(t) - w_meas);
    end
    if ~cascade, Iref = opt.iref(t); end
    % ---- boucle courant (5 kHz)
    if mod(k,ki) == 0
        V = Vnext;                                     % retard d'un échantillon
        [Vnext, pi_i] = pi_step(pi_i, Iref - i);
    end
    % ---- plante continue
    di = (V - P.R*i - P.Ke*w)/opt.L;
    if opt.blocked, dw = 0; else, dw = (P.Kt*i - P.f*w - opt.Cr(t))/opt.J; end
    i = i + di*dt;  w = w + dw*dt;  th = th + w*dt;
    c = floor(th/q);
    if c ~= last_cnt, last_cnt = c; edge = [edge(2) t]; end
    % ---- enregistrement
    if mod(k,dec) == 0 && l < nl
        l = l + 1;
        out.t(l) = t; out.i(l) = i; out.w(l) = w; out.V(l) = V;
        out.Iref(l) = Iref; out.wref(l) = opt.wref(t); out.wmeas(l) = w_meas;
    end
end
end
