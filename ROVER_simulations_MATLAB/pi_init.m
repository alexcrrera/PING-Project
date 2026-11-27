function c = pi_init(Kp, Ki, Ts, lo, hi, n, eint)
% PI_INIT  Crée un correcteur PI discret (vectoriel, n voies).
% lo/hi : saturation de sortie ; eint : seuil d'intégration conditionnelle (Inf = désactivé)
if nargin < 6, n = 1; end
if nargin < 7, eint = Inf; end
c = struct('Kp',Kp,'Ki',Ki,'Ts',Ts,'lo',lo,'hi',hi,'eint',eint,'I',zeros(n,1));
end
