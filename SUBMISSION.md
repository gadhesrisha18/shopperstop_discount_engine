# SUBMISSION.md

## Time Spent by Phase

| Phase | Time | Notes |
|---|---|---|
| Requirements analysis & architecture planning | ~45 min | Reading the spec closely, deciding the Strategy-pattern approach for discount types before writing any code, sketching the module layout |
| Part 1 — Core slab discount engine | ~1 hr | `discounts/base.py` contract, `slab_discount.py`, and the progressive-bracket math, verified against the ₹15,000 example in the spec by hand first |
| Part 2 — Extensible discount framework | ~2 hrs | The other five strategies (flat, percentage, category, buy-X-get-Y, time-based), the factory registry, and `BillService` orchestration (priority ordering, sequential stacking, non-stackable conflicts, max-discount cap) |
| Part 3 — REST API layer | ~1.5 hrs | Routes, Pydantic request/response models, exception handling, correlation-ID middleware, promotion CRUD + activate/deactivate + simulate endpoint |
| Part 4 — Configuration-driven design | ~30 min | `discount_rules.json` schema, wiring tier slabs and stacking rules to load from config rather than being hardcoded |
| Database & seed data | ~40 min | SQLAlchemy models, repository layer, audit log table, `seed.py` demo data covering all six discount types |
| Testing | ~1.5 hrs | 57 tests across unit (strategies, service) and integration (API) levels, chasing coverage from ~75% to 92%+ on the core engine, and specifically re-verifying the three canonical numbers from the spec (₹5,000→₹5,000, ₹15,000→₹13,500, Premium ₹15,000→₹12,000) both in isolation and through the full HTTP stack |
| Documentation (README, DESIGN, TESTING, API_EXAMPLES) | ~1 hr | Written and cross-checked against the actual running code rather than written speculatively — every curl example and coverage number in these docs was run and captured, not estimated |
| Manual verification / bug fixing | ~30 min | Live-testing the app (booting uvicorn, hitting endpoints with curl and TestClient), catching and fixing a stray runtime artifact before packaging |

**Total: ~9 hours** across analysis, implementation, testing, and documentation.

---

## Assumptions Made

1. **Stacking = sequential compounding, not additive percentages.** When multiple discounts stack, each one is applied against the *running total left after prior discounts*, not summed against the original cart value. This was the more conservative interpretation — it composes safely with a hard cap and can never produce a negative or over-discounted bill. This is a genuine judgment call the spec didn't fully pin down, and it's called out explicitly in DESIGN.md rather than silently assumed.
2. **Priority ordering is ascending — lower number runs first.** The base tier slab discount is always priority `0`, so it's treated as the foundational discount that everything else stacks on top of, matching how the assignment frames slab discounts as "the foundation."
3. **"Stackable" is a per-promotion boolean, and only one non-stackable promotion can win per bill.** If two non-stackable promotions are both applicable, the higher-priority one applies and the other is skipped with `non_stackable_conflict` — rather than erroring out or picking arbitrarily.
4. **Buy-X-Get-Y values the "free" units at the cheapest qualifying unit price**, matching common retail POS convention (you don't get to choose the most expensive item as the free one).
5. **The max discount cap (40%) is a global, config-level ceiling**, not a per-promotion setting — it represents a business-wide guardrail ("never discount a bill by more than X%") rather than something marketing sets per campaign. Per-promotion caps (e.g. "15% off, capped at ₹3,000") are supported separately via each strategy's own `params`.
6. **In-memory/embedded SQLite satisfies "no external DB setup"** — I read this as permitting a real (if lightweight) relational database rather than requiring a hand-rolled dict store, since the spec's "Must Have" list separately asks for proper data modeling (audit trail, versioning) that a dict store would make awkward.
7. **Store scoping defaults to "applies everywhere"** when a promotion's `store_ids` list is empty, rather than requiring every promotion to explicitly enumerate every store.

---

## Known Limitations

1. **No authentication/authorization.** Every endpoint is open — there's no distinction between what a Marketing Manager, Store Manager, or System Administrator persona is allowed to do via the API. In production this would need role-based access control, particularly around promotion creation/activation.
2. **No pagination on list endpoints.** `GET /promotions` returns everything matching the filter in one response. Fine at demo scale; would need `limit`/`offset` or cursor-based pagination for a real catalog with hundreds of promotions.
3. **SQLite's file-based mode is single-writer.** Under real concurrent load (many cashiers hitting `/bills/calculate` while marketing edits promotions simultaneously), SQLite's write-locking would become a bottleneck — this is explicitly a reviewer-convenience choice, not a production recommendation (see DESIGN.md §5).
4. **No caching layer**, so every bill calculation re-queries the DB for active promotions. Acceptable at this scale; would matter under real POS throughput.
5. **Buy-X-Get-Y assumes uniform units within one SKU/category match** — it doesn't yet support cross-category bundles (e.g. "buy a shirt, get a tie free").
6. **Time-based discounts use the server's naive datetime** (or an explicit `now` override in the request) rather than store-local timezones — a "Happy Hour 5–8 PM" promotion is currently evaluated in one timezone globally, which would be wrong for a multi-timezone retail chain.
7. **No optimistic concurrency control on promotion updates.** Two admins editing the same promotion simultaneously will have the second write silently overwrite the first (last-write-wins), despite the `version` column existing on the model — it's tracked but not yet enforced.
8. **The audit log records what changed but not a full diff/rollback capability** — you can see that a promotion was updated and by which request, but there's no "revert to previous version" endpoint yet.

---

## What I Would Improve With More Time

1. **Enforce optimistic concurrency** using the existing `version` column — reject an update if the client's expected version doesn't match current state, surfacing a 409 Conflict instead of silently overwriting.
2. **Add RBAC** with distinct scopes matching the five personas (e.g., only Marketing Managers can create/edit promotions; only Store Managers can activate/deactivate for their own store; cashiers only get read access to `/bills/calculate`).
3. **Timezone-aware time-based discounts**, keyed by store location, so "Happy Hour" means the same wall-clock time in every store regardless of server timezone.
4. **A CLI tool** (one of the assignment's "Nice to Have" bonuses) for promotion management, wrapping the same service layer the API uses — useful for scripted bulk promotion setup ahead of a big sale.
5. **Event-driven promotion lifecycle hooks** (e.g., publish an event on activate/deactivate) so downstream systems — POS terminals, the marketing dashboard — could subscribe rather than poll.
6. **Rate limiting** on the mutating promotion endpoints, since a marketing team accidentally scripting a loop of promotion creates/updates could otherwise hammer the API.
7. **Bundle/cross-category Buy-X-Get-Y support**, plus a more general "discount depends on multiple SKUs together" primitive.
8. **Property-based testing** (e.g. via `hypothesis`) for the slab and stacking math specifically — the boundary conditions (exactly at a slab edge, cap exactly reached) are the highest-risk spots for off-by-one bugs, and generative tests would catch cases hand-written examples miss.
9. **Postgres migration path exercised, not just claimed** — actually stand up a docker-compose with Postgres and prove the repository layer needs zero changes, rather than asserting it in DESIGN.md.
10. **A small React or HTMX admin UI** for the Marketing Manager persona specifically, since "configure promotions without coding" is easier to demonstrate with a form than with curl — the API is ready for it, just no UI was built given the take-home's time box.
