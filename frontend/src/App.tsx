import { Routes, Route, Navigate } from "react-router-dom";
import type { ReactElement } from "react";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Conversations from "./pages/Conversations";
import Orders from "./pages/Orders";
import Products from "./pages/Products";
import Login from "./pages/Login";
import { isAuthenticated } from "./api/client";

/**
 * Routing shell. Phase 8: every route except /login now requires a JWT
 * (checked via api/client.ts's isAuthenticated()) — no token redirects
 * to /login instead of rendering the page.
 */
function RequireAuth({ children }: { children: ReactElement }): ReactElement {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout>
              <Dashboard />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/conversations"
        element={
          <RequireAuth>
            <Layout>
              <Conversations />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/orders"
        element={
          <RequireAuth>
            <Layout>
              <Orders />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/products"
        element={
          <RequireAuth>
            <Layout>
              <Products />
            </Layout>
          </RequireAuth>
        }
      />
    </Routes>
  );
}