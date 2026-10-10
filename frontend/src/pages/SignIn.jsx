import { useState } from "react";
import { Navigate } from "react-router-dom";
import { getToken, setToken, signIn, signUp } from "../api/client";

// Sign in or create an account, then keep the token and go to the upload page.

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
      <section className="signin-shell">
        <div className="signin-intro">
          <p className="eyebrow">Document review workspace</p>
          <h1>Turn clinical documents into clear, reviewable insights.</h1>
          <p>
            Upload a discharge summary, identify critical points, and verify medications against your reference
            formulary—all in one place.
          </p>
          <ul className="signin-benefits">
            <li>Source-backed critical points</li>
            <li>Medication and formulary checks</li>
            <li>Fast, structured document summaries</li>
          </ul>
        </div>
        <form className="card signin-card" onSubmit={onSubmit}>
          <div>
            <p className="eyebrow">{mode === "signin" ? "Welcome back" : "Get started"}</p>
            <h2>{mode === "signin" ? "Sign in to your account" : "Create your account"}</h2>
            <p className="hint">
              {mode === "signin" ? "Enter your details to continue." : "Use your work email to create an account."}
            </p>
          </div>
          <label>
            Email address
            <input
              type="email"
              autoComplete="username"
              placeholder="you@company.com"
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
              placeholder="At least 8 characters"
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? <p className="banner error">{error}</p> : null}
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
          <p className="signin-switch">
            {mode === "signin" ? "New to the workspace?" : "Already have an account?"}{" "}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin");
                setError("");
              }}
            >
              {mode === "signin" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </form>
      </section>
    </main>
  );
}
