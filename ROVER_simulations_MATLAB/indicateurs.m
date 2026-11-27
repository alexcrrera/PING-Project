function [tr, D, ts] = indicateurs(t, y, yref, t0)
% INDICATEURS  Temps de montée 10-90 %, dépassement (%), temps d'établissement à 5 %.
m = t >= t0;  t = t(m) - t0;  y = y(m);
tr = t(find(y >= 0.9*yref, 1)) - t(find(y >= 0.1*yref, 1));
D  = max(0, (max(y) - yref)/yref*100);
k  = find(abs(y - yref) > 0.05*abs(yref), 1, 'last');
ts = t(k);
end
