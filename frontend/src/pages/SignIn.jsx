import { useState } from "react";
import { Navigate } from "react-router-dom";
import { getToken, setToken, signIn, signUp } from "../api";

export function SignInPage() {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  if (getToken() || done) return <Navigate to="/" replace />;

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const result = mode === "signin" ? await signIn(email, password) : await signUp(email, password);
      setToken(result.access_token);
      setDone(true);
    } catch (err) {
      setError(err.message);
      setPending(false);
    }
  }

  return (
    <main className="signin">
      <form className="card signin-card" onSubmit={onSubmit}>
        <p className="eyebrow">Meridian Bay</p>
        <h1>Formulary Check</h1>
        <p className="lede">Check a discharge summary against the institutional formulary.</p>
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error ? <p className="banner error">{error}</p> : null}
        <button type="submit" disabled={pending}>
          {pending ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() => {
            setMode(mode === "signin" ? "signup" : "signin");
            setError("");
          }}
        >
          {mode === "signin" ? "Need an account? Create one" : "Already have an account? Sign in"}
        </button>
      </form>
    </main>
  );
}
