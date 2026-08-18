/**
 * Product catalog — list, add, edit.
 *
 * >>> PHASE 10 TARGET — implement once api/client.ts has listProducts <<<
 *
 * TODO:
 * - Grid or table from GET /api/products: image, name, category, price,
 *   stock_qty, is_active toggle.
 * - Add/edit form posting to POST /api/products / PATCH /api/products/{id}.
 * - Low-stock visual indicator (e.g. stock_qty < 5) — this is what the
 *   bot's check_stock tool also reads, so keep them consistent: it's the
 *   raw stock_qty from the same `products` row.
 */
export default function Products() {
  return (
    <div>
      <h1>Products</h1>
      <p>TODO (Phase 10): product catalog — see file header for spec.</p>
    </div>
  );
}
