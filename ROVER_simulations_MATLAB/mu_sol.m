function mu = mu_sol(lam, S)
% MU_SOL  Coefficient d'adhérence longitudinale, magic formula de Pacejka simplifiée.
% mu = D sin(C atan(B lambda)) ; S = struct avec champs B, C, D (vecteur de structs accepté
% si lam est un vecteur de même taille).
if numel(S) == 1
    mu = S.D*sin(S.C*atan(S.B*lam));
else
    mu = zeros(size(lam));
    for j = 1:numel(lam)
        mu(j) = S(j).D*sin(S(j).C*atan(S(j).B*lam(j)));
    end
end
end
