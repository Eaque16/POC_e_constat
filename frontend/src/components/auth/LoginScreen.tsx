import { useState, type FormEvent } from "react";
import { login } from "@/services/auth";
import { ApiError } from "@/services/api";

interface LoginScreenProps {
  onSuccess: () => void;
}

export function LoginScreen({ onSuccess }: LoginScreenProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`${"Connexion \u00e9chou\u00e9e"} (${err.status}) : ${err.message}`);
      } else {
        setError("Impossible de contacter le serveur. Le backend tourne-t-il ?");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-2xl border border-border bg-card p-6"
      >
        <div className="text-center">
          <p className="text-sm font-semibold text-muted-foreground">
            {"ASA-CI TECHNOLOGIE"}
          </p>
          <h1 className="text-lg font-bold">{"ASA CALL CENTER AI"}</h1>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            {"Nom d'utilisateur"}
          </label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            autoFocus
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            {"Mot de passe"}
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Connexion..." : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
