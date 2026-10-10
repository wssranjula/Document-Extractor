/** Signed-in chrome: formulary link, account, and the current page. */

import { useEffect, useState } from "react";
import { Link, Navigate, Outlet, useNavigate } from "react-router-dom";
import { clearToken, currentUser, getToken } from "./api/client";

export function AppShell() {
  const [user, setUser] = useState(undefined);
  const navigate = useNavigate();

  useEffect(() => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    currentUser().then(setUser).catch(() => setUser(null));
  }, []);

  if (user === undefined) return <p className="page-loading">Loading your session…</p>;
  if (!user) return <Navigate to="/login" replace />;

  function signOut() {
    clearToken();
    navigate("/login");
  }

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          Document Review
        </Link>
        <div className="topbar-user">
          <Link to="/references/new" className="topbar-link">
            Add formulary
          </Link>
          <span>{user.email}</span>
          <button type="button" className="text-button" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}
