%% RUN_TRACTION  Boucle de traction (contrôle du glissement) : courbes mu(lambda) + 3 simulations.
% Figures 9 à 12 du cahier de suivi. Test type : consigne roue 0 -> 15 rad/s d'un coup.
clear; close all; clc;
P = params_rover();
Z = @(t) 0;
step15 = @(t) 15*(t >= 0.1);
sols = {'dur','sable','glissant'};
t08 = @(s) temps_seuil(s.t, s.V, 0.8, 0.1);

%% ---------------- Courbes mu(lambda) ----------------
lam = linspace(0,1,400);
figure('Name','Courbes mu(lambda)'); hold on;
for q = 1:3
    S = P.sol.(sols{q}); mu = mu_sol(lam, S); plot(lam, mu);
    [mmax, k] = max(mu);
    fprintf('%-9s : pic lambda = %.2f, mu_max = %.2f, mu(lambda*) = %.2f\n', sols{q}, lam(k), mmax, mu_sol(P.lam_star, S));
end
plot([P.lam_star P.lam_star],[0 0.85],'Color',[.5 .5 .5]);
grid on; xlabel('Glissement \lambda'); ylabel('\mu = F_x / N'); legend([sols, {'\lambda^*'}]);

%% ---------------- T1 : démarrage brutal sur sol glissant ----------------
gl = @(t,x) repmat(P.sol.glissant,1,4);
cas = {struct('tc',false), struct('tc_mode','pi'), struct('tc_mode','ff+pi')};
lab = {'sans contrôle traction','PI seul','limiteur + PI'};
figure('Name','T1 - demarrage sol glissant');
for q = 1:3
    o = cas{q}; o.ext = false; o.ff = false; o.sol = gl; o.direct_w = step15;
    s = sim_rover(P, 1.2, o);
    m = s.t > 0.3 & s.V < 0.8;
    fprintf('T1 %-24s : lambda max = %.2f, lambda moyen = %.2f, 0->0,8 m/s en %.2f s\n', lab{q}, max(s.lam(:,1)), mean(s.lam(m,1)), t08(s));
    subplot(2,1,1); hold on; plot(s.t, s.lam(:,1));
    subplot(2,1,2); hold on; plot(s.t, s.V);
end
subplot(2,1,1); plot([0 1.2],[P.lam_star P.lam_star],':k'); grid on; ylabel('\lambda (roue AvG)'); legend(lab);
subplot(2,1,2); grid on; ylabel('V (m/s)'); xlabel('t (s)');

%% ---------------- T2 : les 3 sols, avec / sans ----------------
figure('Name','T2 - trois sols');
for q = 1:3
    S = P.sol.(sols{q});
    subplot(1,3,q); hold on;
    for tc = [false true]
        s = sim_rover(P, 1.0, struct('tc',tc,'ext',false,'ff',false,'sol',@(t,x) repmat(S,1,4),'direct_w',step15));
        plot(s.t, s.V);
        fprintf('T2 %-9s traction=%d : lambda max = %.2f, 0->0,8 m/s en %.2f s\n', sols{q}, tc, max(s.lam(:,1)), t08(s));
    end
    grid on; title(sols{q}); xlabel('t (s)'); if q == 1, ylabel('V (m/s)'); legend('sans','avec'); end
end

%% ---------------- T3 : qualité de V estimée ----------------
cas = {struct(), struct('v_bias',1.1), struct('v_bias',0.9), struct('est','flux')};
lab = {'V exacte','V +10 %','V -10 %','flux optique brut (20 ms)'};
figure('Name','T3 - sensibilite a V estimee');
for q = 1:4
    o = cas{q}; o.ext = false; o.ff = false; o.direct_w = step15;
    o.sol = gl;                    sg = sim_rover(P, 1.0, o);
    o.sol = @(t,x) repmat(P.sol.dur,1,4); sd = sim_rover(P, 1.0, o);
    m = sg.t > 0.3 & sg.V < 0.8;
    fprintf('T3 %-26s : glissant lambda max = %.2f, moyen = %.2f, t = %.2f s | dur t = %.2f s\n', ...
        lab{q}, max(sg.lam(:,1)), mean(sg.lam(m,1)), t08(sg), t08(sd));
    subplot(1,2,1); hold on; plot(sg.t, sg.lam(:,1));
    subplot(1,2,2); hold on; plot(sd.t, sd.V);
end
s = sim_rover(P, 1.0, struct('tc',false,'ext',false,'ff',false,'direct_w',step15));
subplot(1,2,2); plot(s.t, s.V, 'k:'); grid on; title('Sol dur : V (m/s)'); xlabel('t (s)'); legend([lab, {'sans contrôle'}]);
subplot(1,2,1); grid on; title('Sol glissant : \lambda'); xlabel('t (s)'); legend(lab);
