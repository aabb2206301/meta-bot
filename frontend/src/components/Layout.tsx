import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

/**
 * Nav shell — structure unchanged from the boilerplate (same nav > h2 +
 * ul/li links, same main content area). Phase 8 scope here is styling/
 * branding polish only:
 *   - actual CSS for the "nav-link" / "nav-link-active" classes, which
 *     linkClass() was already producing but which had no rules defined
 *     anywhere, so the active-page highlight silently did nothing.
 *   - basic typography/spacing/color polish.
 * No elements added or removed.
 */
export default function Layout({ children }: { children: ReactNode }) {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? "nav-link nav-link-active" : "nav-link";

  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "system-ui, sans-serif" }}>
      <style>{`
        .nav-link {
          display: block;
          padding: 8px 12px;
          border-radius: 6px;
          color: #444;
          text-decoration: none;
          font-size: 14px;
          transition: background-color 0.15s ease, color 0.15s ease;
        }
        .nav-link:hover {
          background-color: #f2f2f2;
          color: #111;
        }
        .nav-link-active {
          background-color: #111;
          color: #fff;
        }
        .nav-link-active:hover {
          background-color: #111;
          color: #fff;
        }
      `}</style>
      <nav
        style={{
          width: 200,
          borderRight: "1px solid #e5e5e5",
          padding: 20,
          background: "#fafafa",
        }}
      >
        <h2 style={{ fontSize: 16, marginBottom: 24, letterSpacing: "-0.01em" }}>
          AI Sales Agent
        </h2>
        <ul style={{ listStyle: "none", padding: 0, display: "flex", flexDirection: "column", gap: 4 }}>
          <li>
            <NavLink to="/" className={linkClass} end>
              Dashboard
            </NavLink>
          </li>
          <li>
            <NavLink to="/conversations" className={linkClass}>
              Conversations
            </NavLink>
          </li>
          <li>
            <NavLink to="/orders" className={linkClass}>
              Orders
            </NavLink>
          </li>
          <li>
            <NavLink to="/products" className={linkClass}>
              Products
            </NavLink>
          </li>
        </ul>
      </nav>
      <main style={{ flex: 1, padding: 24 }}>{children}</main>
    </div>
  );
}