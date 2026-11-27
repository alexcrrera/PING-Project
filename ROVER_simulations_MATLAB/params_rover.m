% PARAMS_ROVER  Paramètres et gains de la commande du ROVER (partie contrôle).
% Toutes les valeurs côté SORTIE réducteur sauf mention contraire.
% Valeurs arrondies identiques au cahier de suivi (les valeurs exactes sont dans l'Excel).
% Usage : P = params_rover();

function P = params_rover()

%% --- Motoréducteur Pololu 37D 50:1 12 V (datasheet #4753) + hypothèses
P.U_bat = 11.1;        % V    batterie LiPo 3S (hypothèse)
P.R     = 2.2;         % Ohm  = U_n / I_s
P.L     = 2e-3;        % H    (hypothèse, à mesurer)
P.N     = 50;          % rapport de réduction
P.Kt    = 0.37;        % N.m/A  = C_s / I_s (pertes réducteur incluses)
P.Ke    = 0.57;        % V.s/rad = U_n / omega_0
P.f     = 3.5e-3;      % N.m.s/rad frottement visqueux (tiré du courant à vide)
P.J_nom = 9.8e-3;      % kg.m^2  rotor ramené + roue + 1/4 rover
P.J_w   = 2e-6*P.N^2 + 2.7e-4;  % kg.m^2 rotor ramené + roue (sans rover)
P.I_max = 3.0;         % A    limite de courant
P.CPR   = 64*P.N;      % impulsions codeur par tour de roue

%% --- Rover (hypothèses)
P.r = 0.06;  P.e = 0.30;  P.b = 0.30;   % m  rayon, voie, empattement
P.m = 5.0;   P.g = 9.81;
P.Iz = P.m*(P.e^2 + P.b^2)/12;          % kg.m^2
P.mu_lat = 0.5;                         % coefficient de ripage

%% --- Sols (magic formula mu = D sin(C atan(B lambda)) + résistance au roulement)
P.sol.dur      = struct('B',10,'C',1.9,'D',0.80,'crr',0.03);
P.sol.sable    = struct('B',5, 'C',1.5,'D',0.55,'crr',0.12);
P.sol.glissant = struct('B',8, 'C',1.9,'D',0.30,'crr',0.05);

%% --- Fréquences d'échantillonnage
P.Ts_i = 1/5000;  P.Ts_w = 1/500;  P.Ts_l = 1/100;  P.Ts_e = 1/50;

%% --- Gains
% Boucle courant : compensation du pôle électrique, tau_ci = 0,5 ms
P.tau_ci = 0.5e-3;
P.Kp_i = P.L/P.tau_ci;          % 4 V/A
P.Ki_i = P.R/P.tau_ci;          % 4400 V/(A.s)
% Boucle vitesse : placement de omega_c = 100 rad/s, zéro 4x plus bas
P.w_c  = 100;
P.Kp_w = P.J_nom*P.w_c/P.Kt;    % 2,65 A.s/rad
P.Ki_w = P.Kp_w/(4/P.w_c);      % 66 A/rad
% Boucle traction : limiteur + PI sur lambda
P.lam_star = 0.15;
P.EPS      = 0.2;               % m/s  seuil basse vitesse du glissement
P.tau_a    = 1/P.w_c;           % s    anticipation du limiteur
P.Kp_l = 0.22;  P.Ki_l = 22;
% Boucle externe : anticipation + PI (V et lacet)
P.Kp_e = 0.2;   P.Ki_e = 4;
P.eint_V = 0.1; P.eint_P = 0.3; % seuils d'intégration conditionnelle
end
