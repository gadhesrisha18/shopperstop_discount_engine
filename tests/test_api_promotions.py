def _create_flat_promo(client, min_cart_value=3000):
    payload = {
        "name": "Flat 500 off", "discount_type": "FLAT", "description": "test",
        "params": {"amount_off": 500, "min_cart_value": min_cart_value},
        "priority": 50, "stackable": True, "is_active": True,
    }
    return client.post("/api/v1/promotions", json=payload)


def test_create_promotion(client):
    r = _create_flat_promo(client)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Flat 500 off"
    assert body["version"] == 1


def test_create_promotion_invalid_type_rejected(client):
    payload = {
        "name": "Bad promo", "discount_type": "NOT_REAL", "params": {},
    }
    r = client.post("/api/v1/promotions", json=payload)
    assert r.status_code == 422


def test_create_promotion_invalid_params_rejected(client):
    payload = {
        "name": "Bad slab", "discount_type": "SLAB", "params": {"not_slabs": []},
    }
    r = client.post("/api/v1/promotions", json=payload)
    assert r.status_code == 422


def test_get_promotion(client):
    created = _create_flat_promo(client).json()
    r = client.get(f"/api/v1/promotions/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_nonexistent_promotion_404(client):
    r = client.get("/api/v1/promotions/does-not-exist")
    assert r.status_code == 404


def test_list_promotions(client):
    _create_flat_promo(client)
    _create_flat_promo(client)
    r = client.get("/api/v1/promotions")
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_list_promotions_filter_active(client):
    _create_flat_promo(client)
    r = client.get("/api/v1/promotions?is_active=true")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_update_promotion(client):
    created = _create_flat_promo(client).json()
    r = client.put(f"/api/v1/promotions/{created['id']}", json={"name": "Renamed Promo"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed Promo"
    assert r.json()["version"] == 2


def test_activate_deactivate_promotion(client):
    payload = {
        "name": "Inactive promo", "discount_type": "FLAT",
        "params": {"amount_off": 100, "min_cart_value": 0}, "is_active": False,
    }
    created = client.post("/api/v1/promotions", json=payload).json()
    assert created["is_active"] is False

    r = client.post(f"/api/v1/promotions/{created['id']}/activate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    r = client.post(f"/api/v1/promotions/{created['id']}/deactivate")
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_delete_promotion_soft_deletes(client):
    created = _create_flat_promo(client).json()
    r = client.delete(f"/api/v1/promotions/{created['id']}")
    assert r.status_code == 204
    r = client.get(f"/api/v1/promotions/{created['id']}")
    assert r.status_code == 404


def test_simulate_promotion_without_saving(client):
    payload = {
        "promotion": {
            "name": "Draft 10% off", "discount_type": "PERCENTAGE",
            "params": {"rate": 0.10}, "priority": 50, "stackable": True,
        },
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": 10000, "quantity": 1}],
        "customer_tier": "REGULAR",
    }
    r = client.post("/api/v1/promotions/simulate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["final_amount"] < 10000
    # Confirm it wasn't actually saved
    listed = client.get("/api/v1/promotions").json()
    assert listed["total"] == 0


def test_customer_tier_crud(client):
    payload = {
        "id": "GOLD", "label": "Gold Customer",
        "slabs": [{"min": 0, "max": None, "rate": 0.15}],
    }
    r = client.post("/api/v1/customer-tiers", json=payload)
    assert r.status_code == 201

    r = client.get("/api/v1/customer-tiers")
    assert r.status_code == 200
    assert any(t["id"] == "GOLD" for t in r.json())

    r = client.put("/api/v1/customer-tiers/GOLD", json={"label": "Gold Tier Updated"})
    assert r.status_code == 200
    assert r.json()["label"] == "Gold Tier Updated"


def test_bill_calculate_uses_active_promotions(client):
    _create_flat_promo(client, min_cart_value=3000)
    payload = {
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": 5000, "quantity": 1}],
        "customer_tier": "REGULAR",
    }
    r = client.post("/api/v1/bills/calculate", json=payload)
    assert r.status_code == 200
    body = r.json()
    # Slab gives 0 (within first slab), flat promo gives 500 off => 4500
    assert body["final_amount"] == 4500.0
