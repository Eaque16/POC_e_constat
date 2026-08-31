import { api, setToken, clearToken, getToken } from "@/services/api";
import type { TokenResponse } from "@/types/api";

export async function login(
  nomUtilisateur: string,
  motDePasse: string
): Promise<TokenResponse> {
  const result = await api.post<TokenResponse>("/auth/login", {
    nom_utilisateur: nomUtilisateur,
    mot_de_passe: motDePasse,
  });
  setToken(result.access_token);
  return result;
}

export function logout(): void {
  clearToken();
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
