import { KeyRound, User } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Button, Card, Input } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";

export function LoginPage() {
  const { status, login } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (status === "authenticated") {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kutilmagan xatolik");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-bg p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-brand text-xl font-bold text-on-brand">
            Q
          </div>
          <h1 className="mt-4 text-2xl font-semibold">Qurilish CRM</h1>
          <p className="mt-1 text-sm text-muted">Hisobingizga kiring</p>
        </div>
        <Card className="p-6">
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <Input
              label="Login"
              name="username"
              autoComplete="username"
              autoFocus
              required
              icon={<User className="h-4 w-4" />}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <Input
              label="Parol"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              icon={<KeyRound className="h-4 w-4" />}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && (
              <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" loading={loading} disabled={!username || !password}>
              Kirish
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
