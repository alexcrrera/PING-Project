function ts = temps_seuil(t, y, seuil, t0)
% TEMPS_SEUIL  Temps (depuis t0) pour que y dépasse seuil. NaN si jamais atteint.
k = find(y > seuil, 1);
if isempty(k), ts = NaN; else, ts = t(k) - t0; end
end
