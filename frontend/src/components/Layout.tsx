import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

/**
 * Nav shell — complete in the boilerplate (structure + routing links).
 * Phase 8 covers styling/branding polish only, not structural changes.
 */
export default function Layout({ children }: { children: ReactNode }) {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? "nav-link nav-link-active" : "nav-link";

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <nav style={{ width: 200, borderRight: "1px solid #e5e5e5", padding: 16 }}>
        <h2 style={{ fontSize: 16, marginBottom: 24 }}>AI Sales Agent</h2>
        <ul style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
          <li><NavLink to="/" className={linkClass} end>Dashboard</NavLink></li>
          <li><NavLink to="/conversations" className={linkClass}>Conversations</NavLink></li>
          <li><NavLink to="/orders" className={linkClass}>Orders</NavLink></li>
          <li><NavLink to="/products" className={linkClass}>Products</NavLink></li>
        </ul>
      </nav>
      <main style={{ flex: 1, padding: 24 }}>{children}</main>
    </div>
  );
}
