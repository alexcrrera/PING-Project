%% RUN_BOUCLE_INTERNE  Boucle interne (courant + vitesse de roue) : marges + 5 simulations.
% Figures 4 à 8 du cahier de suivi. Durée : quelques secondes sous MATLAB.
clear; close all; clc;
P = params_rover();

%% ---------------- Marges de phase (retard 1,5 Te par boucle) ----------------
tau_e = P.L/P.R;
Li = @(s) P.Kp_i*(1 + 1./(tau_e*s))./(P.R + P.L*s).*exp(-1.5*P.Ts_i*s);
Lw = @(J) @(s) P.Kp_w*(1 + 1./((4/P.w_c)*s)).*(1./(1 + P.tau_ci*s)).*P.Kt./(J*s + P.f).*exp(-1.5*P.Ts_w*s);
J_air = P.J_w;
[wci, pmi]  = marge_phase(Li);
[wcw, pmw]  = marge_phase(Lw(P.J_nom));
[wca, pma]  = marge_phase(Lw(J_air));
[wc2, pm2]  = marge_phase(Lw(2*P.J_nom));
fprintf('--- Gains ---\nKp_i = %.2f V/A, Ki_i = %.0f V/(A.s), Kp_w = %.2f A.s/rad, Ki_w = %.1f A/rad\n', P.Kp_i, P.Ki_i, P.Kp_w, P.Ki_w);
fprintf('--- Marges ---\nCourant          : wc = %6.0f rad/s, PM = %4.1f deg\n', wci, pmi);
fprintf('Vitesse J nom    : wc = %6.0f rad/s, PM = %4.1f deg\n', wcw, pmw);
fprintf('Vitesse roue air : wc = %6.0f rad/s, PM = %4.1f deg\n', wca, pma);
fprintf('Vitesse 2J       : wc = %6.0f rad/s, PM = %4.1f deg\n', wc2, pm2);

%% ---------------- Sim 1 : boucle courant seule, rotor bloqué, échelon 1 A ----------------
o = struct('mode','current','iref',@(t) 1.0*(t >= 1e-3),'blocked',true);
s1 = sim_moteur(P, 5e-3, o);
[tr,D,ts] = indicateurs(s1.t, s1.i, 1, 1e-3);
fprintf('\nSim 1 (courant) : tr = %.2f ms, D = %.1f %%, ts = %.2f ms, Vmax = %.1f V\n', tr*1e3, D, ts*1e3, max(s1.V));
figure('Name','Sim 1 - echelon de courant');
subplot(2,1,1); plot(s1.t*1e3, s1.Iref,'k--', s1.t*1e3, s1.i); grid on; ylabel('Courant (A)'); legend('I_{ref}','I');
subplot(2,1,2); plot(s1.t*1e3, s1.V); grid on; ylabel('V_m (V)'); xlabel('t (ms)');

%% ---------------- Sim 2 : échelon 1 rad/s puis couple de charge 0,3 N.m ----------------
o = struct('wref',@(t) 1.0*(t >= 0.02),'Cr',@(t) 0.3*(t >= 0.3));   % ~ pente 24 deg pour 1/4 du rover
s2 = sim_moteur(P, 0.6, o);
m = s2.t < 0.3;
[tr,D,ts] = indicateurs(s2.t(m), s2.w(m), 1, 0.02);
m = s2.t > 0.3;  dip = 1 - min(s2.w(m));
k = find(abs(s2.w(m) - 1) > 0.05, 1, 'last'); tm = s2.t(m); trec = tm(k) - 0.3;
fprintf('Sim 2 (vitesse) : tr = %.1f ms, D = %.1f %%, ts = %.0f ms ; perturbation : chute %.2f rad/s, retour %.0f ms\n', tr*1e3, D, ts*1e3, dip, trec*1e3);
figure('Name','Sim 2 - echelon de vitesse + perturbation');
subplot(2,1,1); plot(s2.t, s2.wref,'k--', s2.t, s2.w); hold on; plot([0.3 0.3],[0 1.3],':','Color',[.5 .5 .5]); grid on; ylabel('\omega (rad/s)'); legend('\omega_{ref}','\omega');
subplot(2,1,2); plot(s2.t, s2.Iref,'k--', s2.t, s2.i); grid on; ylabel('Courant (A)'); xlabel('t (s)'); legend('I_{ref}','I');

%% ---------------- Sim 3 : grand échelon 0 -> 18 rad/s (saturations) ----------------
o = struct('wref',@(t) 18*(t >= 0.02));
s3 = sim_moteur(P, 0.5, o);
[tr,D,ts] = indicateurs(s3.t, s3.w, 18, 0.02);
fprintf('Sim 3 (grand échelon) : tr = %.0f ms, D = %.1f %%, Imax = %.2f A\n', tr*1e3, D, max(s3.i));
figure('Name','Sim 3 - saturations');
subplot(2,1,1); plot(s3.t, s3.wref,'k--', s3.t, s3.w); grid on; ylabel('\omega (rad/s)'); legend('\omega_{ref}','\omega');
subplot(2,1,2); plot(s3.t, s3.i, s3.t, s3.V/P.U_bat*P.I_max); hold on; plot([0 0.5],[P.I_max P.I_max],'r:'); grid on;
ylabel('Courant (A)'); xlabel('t (s)'); legend('I','V_m normalisée','I_{max}');

%% ---------------- Sim 4 : robustesse J et L ----------------
figure('Name','Sim 4 - robustesse');
subplot(1,2,1); hold on;
Js = [P.J_nom, J_air, 2*P.J_nom]; labJ = {'J nominal','roue en l''air (J/2)','2J'};
for q = 1:3
    o = struct('wref',@(t) 1.0*(t >= 0.02),'J',Js(q));
    s = sim_moteur(P, 0.25, o); plot(s.t, s.w);
    [tr,D,ts] = indicateurs(s.t, s.w, 1, 0.02);
    fprintf('Sim 4 %-22s : tr = %.1f ms, D = %.1f %%, ts = %.0f ms\n', labJ{q}, tr*1e3, D, ts*1e3);
end
grid on; title('Variation de J'); xlabel('t (s)'); ylabel('\omega (rad/s)'); legend(labJ);
subplot(1,2,2); hold on;
Ls = [P.L, P.L/2, 2*P.L]; labL = {'L nominal','L/2','2L'};
for q = 1:3
    o = struct('mode','current','iref',@(t) 1.0*(t >= 5e-4),'blocked',true,'L',Ls(q));
    s = sim_moteur(P, 4e-3, o); plot(s.t*1e3, s.i);
    [tr,D,ts] = indicateurs(s.t, s.i, 1, 5e-4);
    fprintf('Sim 4 %-22s : tr = %.2f ms, D = %.1f %%\n', labL{q}, tr*1e3, D);
end
grid on; title('Variation de L (boucle courant)'); xlabel('t (ms)'); ylabel('I (A)'); legend(labL);

%% ---------------- Sim 5 : mesure de vitesse par comptage vs par période ----------------
wr = @(t) 2*(t >= 0.02);
sC = sim_moteur(P, 0.4, struct('wref',wr,'mesure','comptage'));
sI = sim_moteur(P, 0.4, struct('wref',wr));
sP = sim_moteur(P, 0.4, struct('wref',wr,'mesure','periode'));
m = sC.t > 0.2;
fprintf('Sim 5 : ripple I_ref comptage = %.2f A cc, période = %.2f A cc (résolution comptage %.2f rad/s)\n', ...
    max(sC.Iref(m)) - min(sC.Iref(m)), max(sP.Iref(m)) - min(sP.Iref(m)), 2*pi/P.CPR/P.Ts_w);
figure('Name','Sim 5 - mesure de vitesse');
subplot(2,1,1); plot(sC.t, sC.wmeas,'Color',[.6 .6 .6]); hold on; plot(sC.t, sC.w, sI.t, sI.w,'k--', sP.t, sP.w);
grid on; ylabel('\omega (rad/s)'); legend('\omega mesurée (comptage)','\omega réelle (comptage)','\omega sans quantif.','\omega réelle (période)');
subplot(2,1,2); plot(sC.t, sC.Iref, sP.t, sP.Iref); grid on; ylabel('I_{ref} (A)'); xlabel('t (s)'); legend('comptage','période');
