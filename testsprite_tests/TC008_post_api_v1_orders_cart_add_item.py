import os
import time
import uuid

import requests

BASE_URL = "http://localhost/api/v1"
TIMEOUT = 30


def test_post_api_v1_orders_cart_add_item():
    session = requests.Session()

    # 1. Register a new user
    timestamp = int(time.time())
    email = f"user_{timestamp}@test.com"
    password = os.environ.get("TEST_USER_PASSWORD", "Xq7!mZ2#vL9")
    register_payload = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password
    }
    r = session.post(f"{BASE_URL}/auth/register/", json=register_payload, timeout=TIMEOUT)
    assert r.status_code == 201, f"Register failed: {r.text}"
    access_token = r.json().get("access")
    assert access_token, "No access token returned on register"

    headers_auth = {
        "Authorization": f"Bearer {access_token}"
    }

    # 2. Get products list to obtain a real product_id (uuid)
    products_resp = session.get(f"{BASE_URL}/products/", timeout=TIMEOUT)
    assert products_resp.status_code == 200, f"Get products failed: {products_resp.text}"
    products_json = products_resp.json()
    results = products_json.get("results")
    assert results and isinstance(results, list), "No products results"
    product_id = results[0].get("id")
    assert product_id, "No product id in first product"

    # Define helper to add item to cart
    def add_item_to_cart(payload):
        return session.post(f"{BASE_URL}/orders/cart/add_item/", json=payload, headers=headers_auth, timeout=TIMEOUT)

    # 3. Test adding item with valid product_id and valid quantity and optional personalization fields
    valid_payload = {
        "product_id": product_id,
        "quantity": 1,
        "talla": "M",
        "bordado": "Name",
        "rh": "O+"
    }
    r = add_item_to_cart(valid_payload)
    assert r.status_code == 200, f"Add item valid failed: {r.text}"
    body = r.json()
    # The response is the full Cart with items list, check first item
    items = body.get("items")
    assert items and isinstance(items, list), "No items in cart response"
    first_item = items[0]
    assert first_item.get("product") == product_id, "Returned product id mismatch in cart item"
    assert first_item.get("quantity") == valid_payload["quantity"], "Returned quantity mismatch in cart item"

    # 4. Test adding item with invalid product_id (random UUID)
    invalid_product_id = str(uuid.uuid4())
    invalid_product_payload = {
        "product_id": invalid_product_id,
        "quantity": 1
    }
    r = add_item_to_cart(invalid_product_payload)
    assert r.status_code == 404, f"Expected 404 for invalid product_id, got {r.status_code}"

    # 5. Test adding item with valid product_id but invalid quantity (e.g., very large)
    invalid_quantity_payload = {
        "product_id": product_id,
        "quantity": 1000000
    }
    r = add_item_to_cart(invalid_quantity_payload)
    assert r.status_code == 400, f"Expected 400 for invalid quantity, got {r.status_code}"


test_post_api_v1_orders_cart_add_item()