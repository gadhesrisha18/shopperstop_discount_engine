# DESIGN.md — ShopperStop Promotional Pricing Engine

## 1. Problem framing

The core tension in this assignment is between two requirements that pull in
opposite directions:

- **Part 1** wants a very specific, easy-to-verify calculation: progressive slab
  discounts by customer tier.
- **Part 2–4** want that calculation to be one instance of a much more general,
  configuration-driven, multi-type, stackable discount system that non-engineers
  can operate through APIs.

Building Part 1 as a special case hardcoded into the bill endpoint would have been
the fastest path, but it would fail Part 2 entirely — every new discount type
would mean editing the endpoint. Instead, the slab discount is implemented as
**one interchangeable strategy among six**, so it gets no special treatment in the
orchestration layer. That decision drove most of the rest of the design.

## 2. The Strategy pattern for discount types

`app/discounts/base.py` defines a single abstract contract:

```python
class DiscountStrategy(ABC):
    def is_applicable(self, context: DiscountContext) -> bool: ...
    def calculate(self, context: DiscountContext, running_total: Decimal) -> DiscountResult: ...
```

Every discount type (`SlabDiscount`, `FlatDiscount`, `PercentageDiscount`,
`CategoryDiscount`, `BuyXGetYDiscount`, `TimeBasedDiscount`) implements just these
two methods. `discounts/factory.py` maps a promotion's `discount_type` string to
the right class and constructs it from the promotion's stored `params` dict.

**Why this makes the system extensible:** adding a seventh discount type (say,
"loyalty points redemption") means:
1. Write a new class implementing `DiscountStrategy`.
2. Register its type string in the factory.
3. Nothing else changes — not `BillService`, not the API routes, not the response
   schema (the breakdown is already generic: id, name, type, amount, applied/skipped).

This is the Open/Closed Principle applied directly to the evaluation criteria
("Extensibility — easy to add new discount types").

## 3. Orchestration: `BillService`

`services/bill_service.py` is the only place that knows how *multiple* discounts
combine. Its job, in order:

1. Resolve the customer's tier slabs (config-driven) into an implicit `SLAB`
   strategy for that tier.
2. Load all active promotions applicable to the request's store, tier, and
   timestamp from the repository.
3. Sort every applicable strategy by `priority` ascending.
4. Apply each strategy **sequentially against a running total** — each discount
   sees the cart *after* higher-priority discounts have already reduced it. This
   is what "stacking" means concretely: it's not summing independent percentages
   of the original total, it's compounding against whatever's left.
5. Enforce `stacking_rules.max_total_discount_rate` from `discount_rules.json` as
   a hard ceiling. If the running discount would cross it, the last discount
   applied is trimmed to hit the cap exactly, and the response sets `capped: true`.
6. Return a `DiscountResult` for every strategy considered — including ones that
   were **not** applied and *why* (`skipped_reason`: not_applicable, non_stackable,
   inactive, out_of_window, etc.). This satisfies the Store Cashier persona's need
   for "clear breakdown of discounts applied" and the Finance persona's need for
   attribution.

**Trade-off acknowledged:** sequential/compounding stacking is one of several valid
interpretations of "stacking rules" (an alternative is to sum percentages against
the *original* total, then apply once). I chose compounding because it composes
safely with a hard cap and never produces a negative bill, and it's the more common
real-world POS convention. This is documented rather than silently assumed, since
it's a genuine judgment call, not a spec-mandated behavior.

## 4. Configuration-driven, not hardcoded

Two layers of configuration exist, deliberately kept separate:

- **`config/discount_rules.json`** — the *base* rules that rarely change:
  customer-tier slab definitions and the global stacking policy (max discount %,
  stacking order). This is what a System Administrator would edit and redeploy,
  analogous to environment config.
- **The Promotion table (via the API)** — *dynamic* rules that marketing changes
  daily: individual promotions, their type, parameters, priority, active window,
  store/tier scoping. This is what the Marketing Manager persona operates entirely
  through `POST/PUT/DELETE /api/v1/promotions/*` — no code deploy, no server
  restart, no engineer involved.

This split maps directly to the two different personas who "own" each layer.

## 5. Data layer

SQLAlchemy against **in-memory SQLite** was chosen over a hand-rolled dict store
for three reasons:
1. It gives real relational semantics (soft-delete flags, timestamps, uniqueness)
   without needing a real database process — reviewers run `pip install` and go.
2. It's a one-line change (`DATABASE_URL`) to point at real Postgres/MySQL in
   production — the repository layer doesn't change.
3. It naturally supports the audit log as its own table, joined by entity type/id,
   rather than bolting audit tracking onto an in-memory structure.

## 6. API design choices

- **Versioned from day one** (`/api/v1/...`) — promotional pricing logic changes
  often enough in retail that breaking changes are a when, not an if.
- **Soft delete** for promotions (`DELETE` sets `is_deleted`, doesn't remove the
  row) — Finance needs historical promotions to remain attributable in past bills
  even after marketing retires them.
- **`/promotions/simulate`** is a distinct endpoint from `/bills/calculate` with
  `preview: true` because simulating an *unsaved* promotion draft (marketing
  testing a new idea) and previewing a calculation against *already-saved* active
  promotions (a cashier checking a total before finalizing) are different use
  cases with different payloads — conflating them into one endpoint would make
  both request schemas messier.
- **Idempotency**: bill calculation has no side effects unless the caller acts on
  the result — running the same request twice returns the same breakdown. This is
  true by construction (no writes happen in the calculation path), not something
  that needed separate idempotency-key machinery.

## 7. Error handling

Global exception handlers in `main.py` normalize every error response to
`{error, message, correlation_id, details?}` regardless of where it originated
(Pydantic validation, domain validation, unexpected exceptions) — cashiers'/POS
integrations get a stable contract to branch on instead of parsing free-text
tracebacks.

## 8. What I deliberately did not build

See the README's "What's Not Implemented" section. In short: caching, rate
limiting, and event-driven promotion lifecycle hooks were left out because, at
this scale (in-memory DB, single process, take-home review context), they'd be
speculative complexity rather than something I could demonstrate solving a real
problem — the instructions explicitly warn against over-engineering "for the sake
of it."
