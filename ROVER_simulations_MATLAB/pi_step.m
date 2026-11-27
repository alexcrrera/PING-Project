function [u, c] = pi_step(c, e)
% PI_STEP  Un pas du PI discret (Euler arrière) avec saturation + anti-windup.
% L'intégrateur est gelé si la sortie sature dans le sens de l'erreur
% ou si |e| dépasse le seuil d'intégration conditionnelle.
e  = e(:);
uu = c.Kp*e + c.I;
u  = min(max(uu, c.lo), c.hi);
ok = ~((uu > c.hi & e > 0) | (uu < c.lo & e < 0)) & (abs(e) < c.eint);
c.I = c.I + ok .* (c.Ki*c.Ts*e);
end
