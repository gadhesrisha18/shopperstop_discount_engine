# ShopperStop Promotional Pricing Engine (PPE)

A configurable, API-driven discount engine that replaces ShopperStop's hardcoded
promotional pricing logic. Marketing and operations teams can create, activate, and
combine promotions through REST APIs — no code deployments required.

Built with **Python 3.12 + FastAPI**, an **in-memory SQLite** database (zero setup for
reviewers), and a **Strategy-pattern discount engine** designed to make adding new
discount types a pure addition, never a modification.

---

## Quick Start

### Option 1 — Docker (recommended)

```bash
docker build -t ppe .
docker run -p 8000:8000 ppe
```

### Option 2 — Local

```bash
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

The database is in-memory SQLite and is seeded automatically on startup with:
- Two customer tiers (`REGULAR`, `PREMIUM`) matching the slabs in the spec
- Five demo promotions (flat, category, time-based, buy-x-get-y, and an inactive
  percentage coupon) showing every discount type and the stacking rules in action

No external database, message queue, or paid service is required.

---

## Running Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

57 tests, 93% coverage on `app/` (well above the 80% target on the core engine).
See **TESTING.md** for a full breakdown and how to run specific suites.

---

## Architecture Overview

```
app/
├── main.py                 # FastAPI app, startup/seed, global exception handlers
├── middleware.py            # Correlation-ID middleware for structured logging
├── db.py                    # SQLAlchemy engine/session + ORM models (in-memory SQLite)
├── seed.py                  # Demo data loader (tiers + promotions)
├── config/
│   └── discount_rules.json  # Source of truth for tier slabs + global stacking rules
│
├── discounts/                # The extensible discount engine (Strategy pattern)
│   ├── base.py               #   DiscountStrategy ABC, DiscountContext, DiscountResult
│   ├── slab_discount.py      #   Progressive tiered discount (Part 1 requirement)
│   ├── flat_discount.py      #   ₹X off above a minimum cart value
│   ├── percentage_discount.py#   X% off cart, optional max cap
│   ├── category_discount.py  #   X% off a specific item category
│   ├── bxgy_discount.py      #   Buy-X-Get-Y (free units on qualifying items)
│   ├── time_based_discount.py#   Extra discount within a time window
│   └── factory.py            #   Builds a DiscountStrategy from a stored Promotion row
│
├── repository/
│   └── promotion_repository.py  # DB access for promotions & customer tiers
│
├── services/
│   ├── bill_service.py       # Orchestrates: applicable discounts → priority order →
│   │                         # stacking rules → cap → final breakdown
│   └── promotion_service.py  # CRUD + activate/deactivate + audit trail
│
├── models/
│   ├── request_models.py     # Pydantic request schemas + validation
│   └── response_models.py    # Pydantic response schemas
│
└── routes/
    ├── bill.py                # POST /api/v1/bills/calculate
    ├── promotions.py          # Promotion CRUD, activate/deactivate, /simulate
    └── customer_tiers.py      # Customer tier CRUD
```

### Request flow (bill calculation)

1. `POST /api/v1/bills/calculate` hits `routes/bill.py`, which validates the payload
   against `BillCalculateRequest`.
2. `bill_service.calculate_bill()` loads the customer's tier slab config and every
   **active** promotion applicable to the request's store/tier/time from the repository.
3. Each promotion is turned into a `DiscountStrategy` instance via `discounts/factory.py`.
4. Strategies are sorted by `priority` (ascending — lower runs first) and applied
   **sequentially against a running total**, so later discounts see the effect of
   earlier ones. Each strategy reports whether it applied and why (or why not).
5. The configured stacking rule (`max_total_discount_rate` in `discount_rules.json`)
   is enforced as a hard cap — if the cumulative discount would exceed it, the last
   discount is trimmed and the response is marked `capped: true`.
6. A full breakdown (each discount evaluated, applied or skipped, and why) is returned
   — this is what a cashier or the finance team would need for reconciliation.

`preview: true` in the request (or the dedicated `/promotions/simulate` endpoint) runs
the exact same pipeline without persisting anything — calculation is a pure function of
its inputs, so it's naturally idempotent.

---

## API Summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/bills/calculate` | Calculate a bill with full discount breakdown |
| POST | `/api/v1/promotions` | Create a promotion |
| GET | `/api/v1/promotions` | List promotions (filterable) |
| GET | `/api/v1/promotions/{id}` | Get a promotion |
| PUT | `/api/v1/promotions/{id}` | Update a promotion |
| DELETE | `/api/v1/promotions/{id}` | Soft-delete a promotion |
| POST | `/api/v1/promotions/{id}/activate` | Activate a promotion |
| POST | `/api/v1/promotions/{id}/deactivate` | Deactivate a promotion |
| POST | `/api/v1/promotions/simulate` | Preview a not-yet-saved promotion against a sample cart |
| GET | `/api/v1/customer-tiers` | List customer tiers |
| POST | `/api/v1/customer-tiers` | Create a customer tier |
| PUT | `/api/v1/customer-tiers/{id}` | Update a customer tier |
| GET | `/health` | Health check (app + DB) |

Full interactive documentation (request/response schemas, try-it-out) is auto-generated
at `/docs`. See **API_EXAMPLES.md** for curl walkthroughs of every flow, including the
seven scenarios from the assignment's test table.

---

## Key Design Decisions

See **DESIGN.md** for the full write-up. In brief:

- **Strategy pattern** for discount types — new types are additive (new class +
  factory entry), never touch existing code (Open/Closed principle).
- **Configuration-driven**, not hardcoded — tier slabs and global stacking rules live
  in `config/discount_rules.json`; per-promotion parameters live in the database and
  are editable via the Promotion API without a deploy.
- **In-memory SQLite via SQLAlchemy** — real ORM/relational semantics and zero external
  setup for reviewers; swapping to Postgres is a one-line connection string change.
- **Sequential stacking against a running total** with a configurable priority order
  and a hard percentage cap, so "max 40% off" is enforced regardless of which
  promotions happen to be active.
- **`Decimal` everywhere in money math** — no floating-point rounding surprises in a
  billing system.

---

## What's Not Implemented (and why)

Given this is a take-home assignment, a few "Nice to Have" items were intentionally
left out to keep the codebase focused and reviewable rather than padded:

- No caching layer — with an in-memory DB and no real network/DB latency, caching
  would add complexity without a demonstrable benefit here.
- No rate limiting / feature flags — these are infrastructure concerns better solved
  at the API gateway/ingress layer in a real deployment, not worth faking in-process.
- No event-driven architecture — the audit trail (see `promotion_repository.py`) covers
  the "who changed what, when" requirement without introducing a message broker.

What **is** implemented from "Should Have": audit trail on promotion changes,
correlation-ID structured logging, health checks, and request validation middleware
(global exception handlers in `main.py`).
