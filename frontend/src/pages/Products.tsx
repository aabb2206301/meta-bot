/**
 * Product catalog — list, add, edit.
 *
 * >>> PHASE 10 TARGET — implemented <<<
 *
 * What it does:
 *  - Card grid from GET /api/products: image, name, category, price,
 *    stock_qty, active toggle.
 *  - Add / edit form in a modal posting to POST /api/products /
 *    PATCH /api/products/{id}.
 *  - Low-stock visual indicator at `stock_qty < LOW_STOCK_THRESHOLD`.
 *    This is the same raw column the bot's `check_stock` tool reads,
 *    so the two stay consistent automatically (single source of
 *    truth = the `products` table).
 *  - Category + active-state filters, pagination.
 */
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import {
  createProduct,
  listProducts,
  updateProduct,
  type Product,
  type ProductCreateInput,
  type ProductListResponse,
  type ProductUpdateInput,
} from "../api/client";

const PAGE_SIZE = 20;

// Single source of truth for the low-stock threshold. The bot's
// check_stock tool (tools/product_tools.py) makes its own decision
// on what's "low" — if you change this UI's value, mirror it in the
// tool so they stay in sync.
const LOW_STOCK_THRESHOLD = 5;

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

const ACTIVE_FILTERS = [
  { value: "", label: "All" },
  { value: "true", label: "Active only" },
  { value: "false", label: "Inactive only" },
];

export default function Products() {
  const [categoryFilter, setCategoryFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Product | "new" | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params: {
          category?: string;
          is_active?: boolean;
          page: number;
          page_size: number;
        } = { page, page_size: PAGE_SIZE };
        if (categoryFilter) params.category = categoryFilter;
        if (activeFilter) params.is_active = activeFilter === "true";
        const resp: ProductListResponse = await listProducts(params);
        if (cancelled) return;
        setProducts(resp.items);
        setTotal(resp.total);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [categoryFilter, activeFilter, page]);

  // Category options are derived from the current page's products —
  // good enough for a demo. A real implementation would add a
  // /api/products/categories endpoint, but that's outside Phase 10 scope.
  const categories = Array.from(
    new Set(products.map((p) => p.category).filter((c): c is string => !!c))
  ).sort();

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  async function toggleActive(p: Product, next: boolean) {
    // Optimistic toggle, rollback on failure.
    setProducts((prev) =>
      prev.map((x) => (x.id === p.id ? { ...x, is_active: next } : x))
    );
    try {
      await updateProduct(p.id, { is_active: next });
    } catch (e) {
      setProducts((prev) =>
        prev.map((x) => (x.id === p.id ? { ...x, is_active: p.is_active } : x))
      );
      window.alert((e as Error).message);
    }
  }

  return (
    <div>
      <div style={headerStyle}>
        <h1 style={{ margin: 0 }}>Products</h1>
        <button onClick={() => setEditing("new")} style={primaryButtonStyle}>
          + Add Product
        </button>
      </div>

      <div style={toolbarStyle}>
        <select
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(1);
          }}
          style={selectStyle}
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) => {
            setActiveFilter(e.target.value);
            setPage(1);
          }}
          style={selectStyle}
        >
          {ACTIVE_FILTERS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span style={{ color: "#666", fontSize: 13 }}>
          {total} {total === 1 ? "product" : "products"}
        </span>
      </div>

      {loading ? (
        <p style={{ color: "#666" }}>Loading…</p>
      ) : error ? (
        <p style={{ color: "crimson" }}>Failed to load: {error}</p>
      ) : products.length === 0 ? (
        <div style={emptyStyle}>No products match these filters.</div>
      ) : (
        <div style={gridStyle}>
          {products.map((p) => (
            <ProductCard
              key={p.id}
              product={p}
              onEdit={() => setEditing(p)}
              onToggleActive={(next) => void toggleActive(p, next)}
            />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div style={paginationStyle}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={pageButtonStyle(page === 1)}
          >
            ← Prev
          </button>
          <span style={{ fontSize: 13, color: "#666" }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={pageButtonStyle(page === totalPages)}
          >
            Next →
          </button>
        </div>
      )}

      {editing && (
        <ProductFormModal
          product={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            if (editing === "new") {
              setProducts((prev) => [saved, ...prev]);
              setTotal((t) => t + 1);
            } else {
              setProducts((prev) => prev.map((x) => (x.id === saved.id ? saved : x)));
            }
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function ProductCard({
  product,
  onEdit,
  onToggleActive,
}: {
  product: Product;
  onEdit: () => void;
  onToggleActive: (next: boolean) => void;
}) {
  const isLowStock = product.stock_qty < LOW_STOCK_THRESHOLD;
  return (
    <div style={cardStyle}>
      <div style={imageWrapStyle}>
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} style={imageStyle} />
        ) : (
          <div style={placeholderStyle}>No image</div>
        )}
      </div>
      <div style={cardBodyStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontWeight: 600,
                fontSize: 14,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={product.name}
            >
              {product.name}
            </div>
            {product.category && (
              <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>{product.category}</div>
            )}
          </div>
          <span
            style={{
              ...badgeBase,
              background: product.is_active ? "#dcfce7" : "#fee2e2",
              color: product.is_active ? "#15803d" : "#b91c1c",
            }}
          >
            {product.is_active ? "Active" : "Inactive"}
          </span>
        </div>
        <div style={{ marginTop: 8, fontSize: 18, fontWeight: 600 }}>
          {formatPrice(product.price, product.currency)}
        </div>
        <div
          style={{
            marginTop: 6,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontSize: 13,
              color: isLowStock ? "#b91c1c" : "#444",
              fontWeight: isLowStock ? 600 : 400,
            }}
          >
            {isLowStock ? "⚠ Low stock: " : "Stock: "}
            {product.stock_qty}
          </span>
          <button onClick={onEdit} style={editButtonStyle}>
            Edit
          </button>
        </div>
        <label style={{ marginTop: 8, fontSize: 13, color: "#666", display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={product.is_active}
            onChange={(e) => onToggleActive(e.target.checked)}
          />
          Available
        </label>
      </div>
    </div>
  );
}

function ProductFormModal({
  product,
  onClose,
  onSaved,
}: {
  product: Product | null;
  onClose: () => void;
  onSaved: (saved: Product) => void;
}) {
  const isEdit = !!product;
  const [name, setName] = useState(product?.name ?? "");
  const [description, setDescription] = useState(product?.description ?? "");
  const [category, setCategory] = useState(product?.category ?? "");
  const [price, setPrice] = useState(product?.price != null ? String(product.price) : "");
  const [currency, setCurrency] = useState(product?.currency ?? "INR");
  const [stockQty, setStockQty] = useState(
    product?.stock_qty != null ? String(product.stock_qty) : "0"
  );
  const [imageUrl, setImageUrl] = useState(product?.image_url ?? "");
  const [isActive, setIsActive] = useState(product?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    const priceNum = Number(price);
    if (price === "" || isNaN(priceNum) || priceNum < 0) {
      setError("A non-negative numeric price is required.");
      return;
    }
    const stockNum = parseInt(stockQty, 10);
    if (stockQty !== "" && (isNaN(stockNum) || stockNum < 0)) {
      setError("Stock must be a non-negative integer.");
      return;
    }

    setSaving(true);
    setError(null);
    const body: ProductCreateInput = {
      name: name.trim(),
      description: description.trim() || undefined,
      category: category.trim() || undefined,
      price: priceNum,
      currency: currency || "INR",
      stock_qty: isNaN(stockNum) ? 0 : stockNum,
      image_url: imageUrl.trim() || undefined,
      is_active: isActive,
    };
    try {
      const saved = isEdit && product
        ? await updateProduct(product.id, body as ProductUpdateInput)
        : await createProduct(body);
      onSaved(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={modalBackdropStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ marginTop: 0, marginBottom: 16, fontSize: 18 }}>
          {isEdit ? "Edit Product" : "Add Product"}
        </h2>
        {error && <p style={errorBoxStyle}>{error}</p>}
        <div style={formGridStyle}>
          <Field label="Name *" full>
            <input value={name} onChange={(e) => setName(e.target.value)} style={inputStyle} autoFocus />
          </Field>
          <Field label="Category">
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={inputStyle}
              placeholder="e.g. Apparel"
            />
          </Field>
          <Field label="Price *">
            <input
              type="number"
              step="0.01"
              min="0"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Currency">
            <select value={currency} onChange={(e) => setCurrency(e.target.value)} style={inputStyle}>
              <option>INR</option>
              <option>USD</option>
              <option>EUR</option>
              <option>GBP</option>
            </select>
          </Field>
          <Field label="Stock">
            <input
              type="number"
              min="0"
              value={stockQty}
              onChange={(e) => setStockQty(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Image URL" full>
            <input
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              style={inputStyle}
              placeholder="https://…"
            />
          </Field>
          <Field label="Description" full>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              style={{ ...inputStyle, resize: "vertical", fontFamily: "inherit" }}
            />
          </Field>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, gridColumn: "1 / -1" }}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Active (visible to customers)
          </label>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
          <button onClick={onClose} style={secondaryButtonStyle}>
            Cancel
          </button>
          <button onClick={() => void save()} disabled={saving} style={primaryButtonStyle}>
            {saving ? "Saving…" : isEdit ? "Save changes" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
  full,
}: {
  label: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <label style={{ ...fieldLabelStyle, gridColumn: full ? "1 / -1" : "auto" }}>
      <span style={{ display: "block", marginBottom: 4, color: "#666", fontSize: 12 }}>
        {label}
      </span>
      {children}
    </label>
  );
}

function formatPrice(amount: number, currency: string): string {
  const symbol = CURRENCY_SYMBOLS[currency] ?? `${currency} `;
  return `${symbol}${amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 16,
};

const toolbarStyle: CSSProperties = {
  display: "flex",
  gap: 12,
  marginBottom: 16,
  alignItems: "center",
};

const selectStyle: CSSProperties = {
  padding: "6px 10px",
  border: "1px solid #ddd",
  borderRadius: 4,
  fontSize: 13,
  background: "#fff",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
  gap: 16,
};

const cardStyle: CSSProperties = {
  background: "#fff",
  border: "1px solid #eee",
  borderRadius: 8,
  overflow: "hidden",
  display: "flex",
  flexDirection: "column",
};

const imageWrapStyle: CSSProperties = {
  width: "100%",
  aspectRatio: "4 / 3",
  background: "#fafafa",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  borderBottom: "1px solid #eee",
};

const imageStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
};

const placeholderStyle: CSSProperties = {
  color: "#bbb",
  fontSize: 13,
};

const cardBodyStyle: CSSProperties = {
  padding: 12,
  display: "flex",
  flexDirection: "column",
  gap: 0,
};

const badgeBase: CSSProperties = {
  padding: "2px 6px",
  borderRadius: 4,
  fontSize: 11,
  fontWeight: 600,
  whiteSpace: "nowrap",
  marginLeft: 8,
};

const editButtonStyle: CSSProperties = {
  padding: "4px 10px",
  border: "1px solid #ddd",
  borderRadius: 4,
  background: "#fff",
  color: "#111",
  fontSize: 12,
  cursor: "pointer",
};

const emptyStyle: CSSProperties = {
  padding: 32,
  border: "1px dashed #ddd",
  borderRadius: 8,
  textAlign: "center",
  color: "#666",
  background: "#fafafa",
};

const paginationStyle: CSSProperties = {
  marginTop: 16,
  display: "flex",
  gap: 12,
  alignItems: "center",
  justifyContent: "flex-end",
};

function pageButtonStyle(disabled: boolean): CSSProperties {
  return {
    padding: "6px 12px",
    border: "1px solid #ddd",
    borderRadius: 4,
    background: disabled ? "#f3f4f6" : "#fff",
    color: disabled ? "#9ca3af" : "#111",
    cursor: disabled ? "default" : "pointer",
    fontSize: 13,
  };
}

const modalBackdropStyle: CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: "rgba(0, 0, 0, 0.4)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
};

const modalStyle: CSSProperties = {
  background: "#fff",
  borderRadius: 8,
  padding: 24,
  width: "100%",
  maxWidth: 560,
  maxHeight: "90vh",
  overflow: "auto",
  boxShadow: "0 10px 40px rgba(0, 0, 0, 0.2)",
};

const formGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 12,
};

const fieldLabelStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  fontSize: 13,
};

const inputStyle: CSSProperties = {
  padding: "8px 10px",
  border: "1px solid #ddd",
  borderRadius: 4,
  fontSize: 14,
  background: "#fff",
  fontFamily: "inherit",
};

const errorBoxStyle: CSSProperties = {
  color: "#b91c1c",
  background: "#fee2e2",
  padding: "8px 12px",
  borderRadius: 4,
  fontSize: 13,
  margin: "0 0 12px 0",
};

const primaryButtonStyle: CSSProperties = {
  padding: "8px 16px",
  background: "#111",
  color: "#fff",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 14,
};

const secondaryButtonStyle: CSSProperties = {
  padding: "8px 16px",
  background: "#fff",
  color: "#111",
  border: "1px solid #ddd",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 14,
};
