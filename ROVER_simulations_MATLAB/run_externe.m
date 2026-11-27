%% RUN_EXTERNE  Boucle externe (vitesse V + vitesse de lacet) : 4 simulations.
% Figures 13 à 16 du cahier de suivi. Compare "anticipation seule" et "anticipation + PI".
clear; close all; clc;
P = params_rover();
Z = @(t) 0;
lab = {'anticipation seule','anticipation + PI'};
sable = @(t,x) repmat(P.sol.sable,1,4);

%% ---------------- E1 : échelon V_ref = 0,6 m/s sur sable ----------------
figure('Name','E1 - echelon de vitesse (sable)'); hold on;
for q = 1:2
    s = sim_rover(P, 2.5, struct('Vref',@(t) 0.6*(t >= 0.2),'sol',sable,'ext',q == 2));
    plot(s.t, s.V);
    m = s.t > 2.0;
    k = find(abs(s.V - 0.6) > 0.03, 1, 'last');
    fprintf('E1 %-20s : erreur finale = %.3f m/s, D = %.1f %%, +-5 %% en %.2f s\n', lab{q}, 0.6 - mean(s.V(m)), max(0,(max(s.V)-0.6)/0.6*100), s.t(k) - 0.2);
end
plot(s.t, s.Vref, 'k--'); grid on; ylabel('V (m/s)'); xlabel('t (s)'); legend([lab, {'V_{ref}'}]);

%% ---------------- E2 : échelon de lacet 1 rad/s à V = 0,4 m/s ----------------
figure('Name','E2 - echelon de lacet');
sn = {'dur','sable'};
for j = 1:2
    S = P.sol.(sn{j}); subplot(1,2,j); hold on;
    for q = 1:2
        s = sim_rover(P, 3.0, struct('Vref',@(t) 0.4,'Wref',@(t) 1.0*(t >= 1.0), ...
            'sol',@(t,x) repmat(S,1,4),'ext',q == 2));
        plot(s.t, s.psid);
        m = s.t > 2.5;
        fprintf('E2 %-6s %-20s : psid final = %.2f rad/s, 95 %% en %.2f s\n', sn{j}, lab{q}, mean(s.psid(m)), temps_seuil(s.t, s.psid, 0.95, 1.0));
    end
    plot(s.t, s.Wref, 'k--'); grid on; title(sn{j}); xlabel('t (s)');
    if j == 1, ylabel('d\psi/dt (rad/s)'); legend([lab, {'consigne'}]); end
end

%% ---------------- E3 : pente de 15° sur sable à t = 2 s ----------------
figure('Name','E3 - pente 15 deg (sable)'); hold on;
for q = 1:2
    s = sim_rover(P, 4.5, struct('Vref',@(t) 0.5,'sol',sable,'pente',@(t) (15*pi/180)*(t >= 2.0),'ext',q == 2));
    plot(s.t, s.V);
    m = s.t > 4.0; m2 = s.t > 2.0;
    k = find(m2 & abs(s.V - 0.5) > 0.01, 1, 'last');
    fprintf('E3 %-20s : V finale = %.3f m/s, creux = %.3f m/s, retour +-2 %% en %.2f s\n', lab{q}, mean(s.V(m)), min(s.V(m2)), s.t(k) - 2.0);
end
plot([0 4.5],[0.5 0.5],'k--'); grid on; ylabel('V (m/s)'); xlabel('t (s)'); legend(lab);

%% ---------------- E4 : roues gauches sur zone glissante pendant le démarrage ----------------
patch = @(t,x) zone_gauche(P, x);
cas = {struct('tc',false,'ext',false), struct('ext',false), struct()};
lab4 = {'ni traction ni PI','traction seule','traction + PI externe'};
figure('Name','E4 - zone glissante a gauche');
for q = 1:3
    o = cas{q}; o.Vref = @(t) 0.8*(t >= 0.1); o.sol = patch;
    s = sim_rover(P, 2.5, o);
    psi = cumsum(s.psid)*(s.t(2) - s.t(1));
    fprintf('E4 %-22s : |psid| max = %.2f rad/s, cap final = %.2f deg\n', lab4{q}, max(abs(s.psid)), psi(end)*180/pi);
    subplot(2,1,1); hold on; plot(s.t, s.psid);
    subplot(2,1,2); hold on; plot(s.t, psi*180/pi);
end
subplot(2,1,1); grid on; ylabel('d\psi/dt (rad/s)'); legend(lab4);
subplot(2,1,2); grid on; ylabel('cap \psi (deg)'); xlabel('t (s)');
