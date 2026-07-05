def test_calculate_basic_slab(client):
    payload = {
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": 5000, "quantity": 1}],
        "customer_tier": "REGULAR",
    }
    r = client.post("/api/v1/bills/calculate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["final_amount"] == 5000.0
    assert body["total_discount"] == 0.0
    assert "correlation_id" in body


def test_calculate_multi_slab(client):
    payload = {
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": 15000, "quantity": 1}],
        "customer_tier": "REGULAR",
    }
    r = client.post("/api/v1/bills/calculate", json=payload)
    assert r.status_code == 200
    assert r.json()["final_amount"] == 13500.0


def test_calculate_premium(client):
    payload = {
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": 15000, "quantity": 1}],
        "customer_tier": "PREMIUM",
    }
    r = client.post("/api/v1/bills/calculate", json=payload)
    assert r.status_code == 200
    assert r.json()["final_amount"] == 12000.0


def test_invalid_negative_price_returns_422(client):
    payload = {
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": -100, "quantity": 1}],
        "customer_tier": "REGULAR",
    }
    r = client.post("/api/v1/bills/calculate", json=payload)
    assert r.status_code == 422
    body = r.json()
    assert "error" in body


def test_empty_cart_returns_422(client):
    payload = {"cart_items": [], "customer_tier": "REGULAR"}
    r = client.post("/api/v1/bills/calculate", json=payload)
    assert r.status_code == 422


def test_unknown_customer_tier_returns_422(client):
    payload = {
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": 1000, "quantity": 1}],
        "customer_tier": "DIAMOND",
    }
    r = client.post("/api/v1/bills/calculate", json=payload)
    assert r.status_code == 422


def test_correlation_id_echoed_from_header(client):
    payload = {
        "cart_items": [{"sku": "S1", "name": "Item", "category": "General", "unit_price": 1000, "quantity": 1}],
        "customer_tier": "REGULAR",
    }
    r = client.post("/api/v1/bills/calculate", json=payload, headers={"X-Correlation-Id": "test-corr-123"})
    assert r.status_code == 200
    assert r.json()["correlation_id"] == "test-corr-123"
    assert r.headers["X-Correlation-Id"] == "test-corr-123"


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
