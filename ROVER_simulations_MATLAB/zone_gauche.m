function S = zone_gauche(P, x)
% ZONE_GAUCHE  Roues gauches sur sol glissant pour x < 0,6 m, le reste sur sol dur.
if x < 0.6, g = P.sol.glissant; else, g = P.sol.dur; end
S = [g, g, P.sol.dur, P.sol.dur];
end
