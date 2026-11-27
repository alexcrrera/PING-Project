function [wc, pm] = marge_phase(Lfun)
% MARGE_PHASE  Pulsation de coupure (|L| = 1) et marge de phase (deg) d'une
% fonction de transfert en boucle ouverte donnée comme handle @(s).
% (Pas besoin de la Control System Toolbox.)
w  = logspace(-1, 5, 200000);
Lw = Lfun(1j*w);
k  = find(diff(sign(abs(Lw) - 1)) ~= 0, 1);
wc = w(k);
ph = unwrap(angle(Lw));
pm = 180 + ph(k)*180/pi;
end
