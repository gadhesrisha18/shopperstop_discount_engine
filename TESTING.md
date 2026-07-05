# TESTING.md

## Running the suite

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

With coverage (matches CI-style output):

```bash
python -m pytest tests/ --cov=app --cov-report=term-missing
```

Run a single file or test:

```bash
python -m pytest tests/test_slab_discount.py -v
python -m pytest tests/test_bill_service.py::TestBillServiceCore::test_regular_15000_multi_slab -v
```

## Current results

```
57 passed
Coverage: 92-93% on app/  (target: 80% on core engine)
```

Core engine modules (`discounts/*`, `services/bill_service.py`) sit at 91-100%
coverage individually — the only meaningfully under-covered file is `seed.py`
(60%, demo data loader, not part of the "core engine").

## Test organization

| File | Covers |
|---|---|
| `tests/test_slab_discount.py` | Pure slab-discount math in isolation (Part 1 foundation) — every boundary, zero-cart, and cap-to-running-total edge case |
| `tests/test_other_discounts.py` | Each of the other five discount types (flat, percentage, category, buy-x-get-y, time-based) in isolation |
| `tests/test_bill_service.py` | Orchestration: multi-discount stacking, non-stackable conflicts, the max-discount cap, tier scoping, rounding |
| `tests/test_api_bills.py` | `POST /bills/calculate` over HTTP — validation errors, correlation IDs, health check |
| `tests/test_api_promotions.py` | Full promotion & customer-tier CRUD lifecycle over HTTP, activate/deactivate, soft delete, simulate |

## Assignment test-scenario mapping

The seven scenarios from the assignment's "Test Scenarios" table map to these tests:

| # | Scenario | Expected | Test |
|---|---|---|---|
| 1 | Basic slab discount — Regular, ₹5,000 | ₹5,000 (no discount) | `test_slab_discount.py::test_within_first_slab_no_discount`, `test_bill_service.py::test_regular_5000_no_discount` |
| 2 | Multi-slab calculation — Regular, ₹15,000 | ₹13,500 | `test_slab_discount.py::test_multi_slab_15000`, `test_bill_service.py::test_regular_15000_multi_slab` |
| 3 | Premium customer — Premium, ₹15,000 | ₹12,000 | `test_slab_discount.py::test_premium_15000`, `test_bill_service.py::test_premium_15000` |
| 4 | Stacked discounts — Premium, ₹20,000 + coupon | Stacking-rule-compliant total | `test_bill_service.py::test_stacked_flat_discount_on_top_of_slab`, `test_non_stackable_conflict_only_one_wins` |
| 5 | Time-based promotion — Happy Hour | Extra time-window discount applied | `test_other_discounts.py::TestTimeBasedDiscount` |
| 6 | Maximum cap reached — Premium, ₹50,000 + multiple promos | Capped at configured max rate | `test_bill_service.py::test_max_discount_cap_enforced` |
| 7 | Invalid inputs — negative amount | 422 with meaningful error | `test_api_bills.py::test_invalid_negative_price_returns_422`, `test_bill_service.py::test_negative_price_rejected` |

## Notes on test design

- **Unit tests bypass the API/DB** where possible (`test_slab_discount.py`,
  `test_other_discounts.py`) so the discount math is verified in complete isolation
  from HTTP, ORM, and seed-data concerns — a failure there points at exactly one thing.
- **`test_bill_service.py`** tests the orchestration layer directly against
  in-memory `DiscountStrategy` instances (no HTTP), so stacking/cap/rounding logic
  is verified without network or serialization noise.
- **`test_api_*.py`** exercise the full stack through FastAPI's `TestClient` (via
  `tests/conftest.py`, which spins up a fresh in-memory DB per test) — this is what
  actually proves the REST contract works end-to-end.
- All money assertions use `Decimal`, matching production code, to catch any
  accidental float rounding regressions.
