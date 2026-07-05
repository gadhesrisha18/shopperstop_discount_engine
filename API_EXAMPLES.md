# API_EXAMPLES.md

All examples assume the server is running locally on port 8000:

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive equivalents are always available at `http://localhost:8000/docs`.

---

## 1. Bill Calculation

### 1a. Basic slab discount — Regular customer, ₹5,000 (no discount expected)

```bash
curl -s -X POST http://localhost:8000/api/v1/bills/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": 5000, "quantity": 1}],
    "customer_tier": "REGULAR"
  }'
```
Expect `cart_subtotal: 5000`. Note: seed data includes a stackable "flat ₹500 off
above ₹3,000" promotion that will also apply on top of the slab result — pass
`"coupon_codes": []` and check `discounts_breakdown` to see each discount's
individual contribution, or deactivate demo promotions first (see §2d) for a
pure slab-only comparison.

### 1b. Multi-slab calculation — Regular, ₹15,000 → ₹13,500

```bash
curl -s -X POST http://localhost:8000/api/v1/bills/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": 15000, "quantity": 1}],
    "customer_tier": "REGULAR"
  }'
```

### 1c. Premium customer — ₹15,000 → ₹12,000

```bash
curl -s -X POST http://localhost:8000/api/v1/bills/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": 15000, "quantity": 1}],
    "customer_tier": "PREMIUM"
  }'
```

### 1d. Time-based promotion — Happy Hour (5–8 PM)

```bash
curl -s -X POST http://localhost:8000/api/v1/bills/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": 10000, "quantity": 1}],
    "customer_tier": "REGULAR",
    "now": "2026-07-03T18:00:00"
  }'
```
The `now` override lets you test time-based logic deterministically without
waiting for the actual clock — response will show `promo-happy-hour` applied.

### 1e. Maximum cap reached — Premium, ₹50,000, multiple promos

```bash
curl -s -X POST http://localhost:8000/api/v1/bills/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": 50000, "quantity": 1}],
    "customer_tier": "PREMIUM",
    "now": "2026-07-03T18:00:00"
  }'
```
Check `"capped": true` and `"cap_rate"` in the response — the cumulative discount
is trimmed to `stacking_rules.max_total_discount_rate` (40%) from
`config/discount_rules.json`, regardless of how many promotions would otherwise apply.

### 1f. Invalid input — negative price

```bash
curl -s -X POST http://localhost:8000/api/v1/bills/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": -100, "quantity": 1}],
    "customer_tier": "REGULAR"
  }'
```
Returns `422` with `{"error": "VALIDATION_ERROR", ...}` and field-level detail.

### 1g. Preview mode (idempotent, no side effects)

```bash
curl -s -X POST http://localhost:8000/api/v1/bills/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": 8000, "quantity": 1}],
    "customer_tier": "REGULAR",
    "preview": true
  }'
```

---

## 2. Promotion Management

### 2a. Create a promotion (15% off entire cart, Electronics-store-only)

```bash
curl -s -X POST http://localhost:8000/api/v1/promotions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Diwali 15% Off",
    "discount_type": "PERCENTAGE",
    "description": "15% off entire cart, storewide",
    "params": {"rate": 0.15, "max_discount_amount": 3000},
    "priority": 20,
    "stackable": true,
    "is_active": false
  }'
```
Save the returned `id` for the calls below.

### 2b. List promotions (with filters)

```bash
curl -s "http://localhost:8000/api/v1/promotions?is_active=true"
```

### 2c. Get a single promotion

```bash
curl -s http://localhost:8000/api/v1/promotions/promo-flat-500
```

### 2d. Update a promotion

```bash
curl -s -X PUT http://localhost:8000/api/v1/promotions/promo-flat-500 \
  -H "Content-Type: application/json" \
  -d '{"priority": 10}'
```

### 2e. Activate / deactivate

```bash
curl -s -X POST http://localhost:8000/api/v1/promotions/promo-coupon10/activate
curl -s -X POST http://localhost:8000/api/v1/promotions/promo-coupon10/deactivate
```

### 2f. Soft delete

```bash
curl -s -X DELETE http://localhost:8000/api/v1/promotions/promo-bxgy-shirts -w "\nStatus: %{http_code}\n"
```
Returns `204`. The promotion row remains for audit/history purposes with
`is_deleted = true` — it just no longer participates in bill calculation.

---

## 3. Promotion Simulation (marketing preview, not-yet-saved)

```bash
curl -s -X POST http://localhost:8000/api/v1/promotions/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "promotion": {
      "name": "Draft: Flash Sale 20%",
      "discount_type": "PERCENTAGE",
      "params": {"rate": 0.20},
      "priority": 5,
      "stackable": true
    },
    "cart_items": [{"sku": "S1", "name": "Item", "unit_price": 12000, "quantity": 1}],
    "customer_tier": "REGULAR"
  }'
```
Runs the exact same calculation pipeline as `/bills/calculate` but against a
draft promotion that has never been persisted — nothing is written to the DB.

---

## 4. Customer Tier Management

### 4a. List tiers

```bash
curl -s http://localhost:8000/api/v1/customer-tiers
```

### 4b. Create a new tier (e.g., a VIP tier above Premium)

```bash
curl -s -X POST http://localhost:8000/api/v1/customer-tiers \
  -H "Content-Type: application/json" \
  -d '{
    "id": "VIP",
    "label": "VIP Customer",
    "slabs": [
      {"min": 0, "max": 5000, "rate": 0.15},
      {"min": 5000, "max": 10000, "rate": 0.25},
      {"min": 10000, "max": null, "rate": 0.35}
    ]
  }'
```

### 4c. Update a tier's slabs

```bash
curl -s -X PUT http://localhost:8000/api/v1/customer-tiers/VIP \
  -H "Content-Type: application/json" \
  -d '{"slabs": [{"min": 0, "max": 5000, "rate": 0.20}, {"min": 5000, "max": null, "rate": 0.35}]}'
```

---

## 5. System

```bash
curl -s http://localhost:8000/health
```
```json
{"status": "ok", "version": "1.0.0", "db": "ok"}
```

---

## Postman

Every endpoint above is also documented interactively via OpenAPI at
`http://localhost:8000/docs` — importable directly into Postman via
**Import → Link → `http://localhost:8000/openapi.json`** once the server is running.
