import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { login, setToken } from "../api/client";

/**
 * Minimal login page.
 *
 * NOTE: this file was NOT in IMPLEMENTATION_PLAN.md's Phase 8 file list
 * (only client.ts, App.tsx, and Layout.tsx were). It's added here because
 * App.tsx's "redirect to login when no JWT is present" requirement has
 * nowhere to redirect to without it — confirmed with the user before
 * adding it rather than assuming it already existed in the scaffold.
 */
export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await login(email, password);
      setToken(res.access_token);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        alignItems: "center",
        justifyContent: "center",
        background: "#fafafa",
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: 320,
          padding: 28,
          background: "#fff",
          border: "1px solid #e5e5e5",
          borderRadius: 10,
          boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        }}
      >
        <h1 style={{ fontSize: 18, marginBottom: 4 }}>AI Sales Agent</h1>
        <p style={{ fontSize: 13, color: "#666", marginBottom: 20 }}>Sign in to the dashboard</p>

        <label style={{ display: "block", marginBottom: 12, fontSize: 13 }}>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            style={{
              display: "block",
              width: "100%",
              padding: "8px 10px",
              marginTop: 4,
              border: "1px solid #ddd",
              borderRadius: 6,
              fontSize: 14,
              boxSizing: "border-box",
            }}
          />
        </label>

        <label style={{ display: "block", marginBottom: 16, fontSize: 13 }}>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{
              display: "block",
              width: "100%",
              padding: "8px 10px",
              marginTop: 4,
              border: "1px solid #ddd",
              borderRadius: 6,
              fontSize: 14,
              boxSizing: "border-box",
            }}
          />
        </label>

        {error && (
          <p style={{ color: "#c0392b", fontSize: 13, marginBottom: 12 }}>{error}</p>
        )}

        <button
          type="submit"
          disabled={submitting}
          style={{
            width: "100%",
            padding: "10px 0",
            border: "none",
            borderRadius: 6,
            background: submitting ? "#999" : "#111",
            color: "#fff",
            fontSize: 14,
            cursor: submitting ? "default" : "pointer",
          }}
        >
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}