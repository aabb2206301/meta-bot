import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Conversations from "./pages/Conversations";
import Orders from "./pages/Orders";
import Products from "./pages/Products";

/**
 * Routing shell — complete in the boilerplate. Wire this to real auth
 * (redirect to a login page when no JWT is present) in Phase 8, since
 * that's the same phase that finishes api/client.ts's auth handling.
 */
export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/conversations" element={<Conversations />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/products" element={<Products />} />
      </Routes>
    </Layout>
  );
}
