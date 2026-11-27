function out = sim_rover(P, T, opt)
% SIM_ROVER  Simulation du rover complet (4 roues, skid-steer) avec les 4 étages :
% courant (5 kHz) -> vitesse roue (500 Hz) -> traction (100 Hz) -> externe (50 Hz).
% Roues : 1 = AvG, 2 = ArG, 3 = AvD, 4 = ArD.
%
% opt (champs optionnels) :
%   Vref, Wref  @(t) consignes de vitesse (m/s) et de lacet (rad/s)     défaut 0
%   sol         @(t,x) -> vecteur de 4 structs sol (cf. P.sol)          défaut sol dur
%   pente       @(t) angle de pente (rad)                               défaut 0
%   tc          true/false : contrôle de traction                       défaut true
%   tc_mode     'ff+pi' (limiteur + PI, défaut), 'ff' ou 'pi'
%   ext         true/false : PI de la boucle externe                    défaut true
%   ff          true/false : anticipation de la consigne externe        défaut true
%   direct_w    @(t) consigne roue directe (bypasse la boucle externe)  défaut []
%   est         'fusion' (V estimée sans retard, défaut) ou 'flux' (flux optique brut, retard 20 ms)
%   v_bias      facteur de biais sur V estimée                          défaut 1
%   anticip     horizon d'anticipation du limiteur (s)                  défaut P.tau_a
%   seed        graine du bruit                                         défaut 0

d = struct('Vref',@(t) 0,'Wref',@(t) 0,'sol',@(t,x) repmat(P.sol.dur,1,4),'pente',@(t) 0, ...
    'tc',true,'tc_mode','ff+pi','ext',true,'ff',true,'direct_w',[],'est','fusion', ...
    'v_bias',1,'anticip',P.tau_a,'seed',0);
fn = fieldnames(d);
for q = 1:numel(fn), if ~isfield(opt,fn{q}), opt.(fn{q}) = d.(fn{q}); end, end
rng(opt.seed);

dt = 2e-5;  n = round(T/dt);
ki = round(P.Ts_i/dt); kw = round(P.Ts_w/dt); kl = round(P.Ts_l/dt); ke = round(P.Ts_e/dt);
side = [-1; -1; 1; 1];
slip = @(rw, v) (rw - v)./max(max(abs(rw), abs(v)), P.EPS);

pi_i = pi_init(P.Kp_i, P.Ki_i, P.Ts_i, -P.U_bat, P.U_bat, 4);
pi_w = pi_init(P.Kp_w, P.Ki_w, P.Ts_w, -P.I_max, P.I_max, 4);
pi_l = pi_init(P.Kp_l, P.Ki_l, P.Ts_l, -1, 0, 4);
pi_V = pi_init(P.Kp_e, P.Ki_e, P.Ts_e, -1, 1, 1, P.eint_V);
pi_P = pi_init(P.Kp_e, P.Ki_e, P.Ts_e, -3, 3, 1, P.eint_P);

i = zeros(4,1); w = zeros(4,1); V = 0; psid = 0; x = 0; dV = 0;
Vcmd = zeros(4,1); Iref = zeros(4,1); Inext = zeros(4,1);
wref = zeros(4,1); wref_p = zeros(4,1); u_l = zeros(4,1); lam_est = zeros(4,1);
buf = [0 0]; Vhat = 0; psid_hat = 0;

dec = 50; nl = floor(n/dec); l = 0;
out.t = zeros(nl,1); out.V = out.t; out.psid = out.t; out.x = out.t; out.Vref = out.t; out.Wref = out.t;
out.w = zeros(nl,4); out.lam = out.w; out.lam_est = out.w; out.F = out.w; out.I = out.w; out.wref = out.w; out.wref_p = out.w;

for k = 0:n-1
    t = k*dt;
    %% ---- capteurs + boucle externe (50 Hz)
    if mod(k,ke) == 0
        buf = [buf(2), opt.v_bias*V + 0.01*randn];  Vflow = buf(1);   % flux optique : 1 période de retard
        if strcmp(opt.est,'flux'), Vhat = Vflow; else, Vhat = opt.v_bias*V + 0.01*randn; end
        psid_hat = psid + 0.01*randn;                                    % gyro
        Vr = opt.Vref(t); Wr = opt.Wref(t);
        Vc = 0; Wc = 0;
        if opt.ff, Vc = Vr; Wc = Wr; end
        if opt.ext
            [uV, pi_V] = pi_step(pi_V, Vr - Vhat);     Vc = Vc + uV;
            [uP, pi_P] = pi_step(pi_P, Wr - psid_hat); Wc = Wc + uP;
        end
        if ~opt.ext && ~opt.ff, Vc = Vr; Wc = Wr; end
        wref = min(max((Vc + side*Wc*P.e/2)/P.r, -19), 19);          % cinématique inverse
        if ~isempty(opt.direct_w), wref = opt.direct_w(t)*ones(4,1); end
    end
    %% ---- boucle traction (100 Hz)
    if mod(k,kl) == 0
        vw_hat  = Vhat + side*psid_hat*P.e/2;
        lam_est = slip(P.r*w, vw_hat);
        base = wref;
        if opt.tc && ~isempty(strfind(opt.tc_mode,'ff'))            % limiteur direct
            a_imu = dV + 0.05*randn;
            va = abs(vw_hat + a_imu*opt.anticip);
            w_lim = max(va/(1 - P.lam_star), va + P.lam_star*P.EPS)/P.r;
            base = sign(wref).*min(abs(wref), w_lim);
        end
        if opt.tc && ~isempty(strfind(opt.tc_mode,'pi'))            % PI sur lambda
            [u_l, pi_l] = pi_step(pi_l, P.lam_star - lam_est.*sign(wref + 1e-9));
        end
        wref_p = base.*(1 + u_l);
    end
    %% ---- boucle vitesse roue (500 Hz)
    if mod(k,kw) == 0
        Iref = Inext;
        [Inext, pi_w] = pi_step(pi_w, wref_p - w);
    end
    %% ---- boucle courant (5 kHz)
    if mod(k,ki) == 0
        [Vcmd, pi_i] = pi_step(pi_i, Iref - i);
    end
    %% ---- physique
    th  = opt.pente(t);
    Nz  = P.m*P.g*cos(th)/4;
    vw  = V + side*psid*P.e/2;
    lam = slip(P.r*w, vw);
    S   = opt.sol(t, x);
    F   = mu_sol(lam, S)*Nz;  F = F(:);
    crr = mean([S.crr]);
    di  = (Vcmd - P.R*i - P.Ke*w)/P.L;
    dw  = (P.Kt*i - P.f*w - P.r*F)/P.J_w;
    dV  = (sum(F) - P.m*P.g*(sin(th) + crr*cos(th)*tanh(V/0.02)))/P.m;
    Mr  = P.mu_lat*P.m*P.g*cos(th)*P.b/4*tanh(psid/0.05);
    dps = (P.e/2*(F(3) + F(4) - F(1) - F(2)) - Mr)/P.Iz;
    i = i + di*dt; w = w + dw*dt; V = V + dV*dt; psid = psid + dps*dt; x = x + V*dt;
    %% ---- enregistrement
    if mod(k,dec) == 0 && l < nl
        l = l + 1;
        out.t(l) = t; out.V(l) = V; out.psid(l) = psid; out.x(l) = x;
        out.Vref(l) = opt.Vref(t); out.Wref(l) = opt.Wref(t);
        out.w(l,:) = w; out.lam(l,:) = lam; out.lam_est(l,:) = lam_est; out.F(l,:) = F;
        out.I(l,:) = i; out.wref(l,:) = wref; out.wref_p(l,:) = wref_p;
    end
end
end
