import os
import time
import uuid

import requests

BASE_URL = "http://localhost:80/api/v1"
PASSWORD = os.environ.get("TEST_USER_PASSWORD", "Xq7!mZ2#vL9")

def test_post_api_v1_orders_cart_add_item():
    session = requests.Session()
    timeout = 30

    # Step 1: Register a unique user
    timestamp = int(time.time() * 1000)
    email = f"user_{timestamp}@test.com"
    register_data = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": PASSWORD,
        "password2": PASSWORD
    }
    r = session.post(f"{BASE_URL}/auth/register/", json=register_data, timeout=timeout)
    assert r.status_code == 201, f"Registration failed with status {r.status_code}, body: {r.text}"
    access_token = r.json().get("access")
    assert access_token, "No access token returned on register"

    headers = {"Authorization": f"Bearer {access_token}"}

    # Step 2: Get a valid product to use for cart add_item
    r = session.get(f"{BASE_URL}/products/", timeout=timeout)
    assert r.status_code == 200, f"Failed to get products list, status {r.status_code}"
    data = r.json()
    results = data.get("results")
    assert results and isinstance(results, list) and len(results) > 0, "No products found in product list"
    product_id = results[0].get("id")
    assert product_id, "Product does not have id field"

    # Initialize to None for cleanup
    created_item_id = None

    try:
        # 3a. Success case: add item with valid product_id, quantity, and optional customization fields
        payload = {
            "product_id": product_id,
            "quantity": 2,
            "talla": "M",
            "bordado": "Test embroidery",
            "rh": "O+"
        }
        r = session.post(f"{BASE_URL}/orders/cart/add_item/", json=payload, headers=headers, timeout=timeout)
        assert r.status_code == 201, f"Adding item to cart failed with status {r.status_code}, body: {r.text}"
        cart = r.json()
        # Validate cart structure minimally
        assert isinstance(cart, dict), "Cart response is not a JSON object"
        assert "items" in cart and isinstance(cart["items"], list), "Cart has no items list"
        assert any(item.get("product") == product_id or item.get("product_id") == product_id for item in cart["items"]), "Added product not in cart items"
        assert cart.get("total_items") >= 1, "Cart total_items less than 1"
        assert "subtotal" in cart, "Cart subtotal missing"

        # Save created cart item id to use for cleanup if needed
        # The cart itself has no id for items to delete individually, so cleanup will be to empty cart if possible - no API endpoint to delete item mentioned.
        # We'll skip deletion since cart is user-specific and this is test env

        # 3b. Error case: invalid product_id (random UUID)
        invalid_product_id = str(uuid.uuid4())
        payload_invalid_product = {
            "product_id": invalid_product_id,
            "quantity": 2
        }
        r = session.post(f"{BASE_URL}/orders/cart/add_item/", json=payload_invalid_product, headers=headers, timeout=timeout)
        assert r.status_code == 404, f"Expected 404 for invalid product_id but got {r.status_code}"

        # 3c. Error case: invalid quantity (0)
        payload_invalid_quantity = {
            "product_id": product_id,
            "quantity": 0
        }
        r = session.post(f"{BASE_URL}/orders/cart/add_item/", json=payload_invalid_quantity, headers=headers, timeout=timeout)
        assert r.status_code == 400, f"Expected 400 for invalid quantity 0 but got {r.status_code}"

        # 3c_alt. Error case: invalid quantity (exceeding stock - use a large number e.g. 999999)
        payload_invalid_quantity2 = {
            "product_id": product_id,
            "quantity": 999999
        }
        r = session.post(f"{BASE_URL}/orders/cart/add_item/", json=payload_invalid_quantity2, headers=headers, timeout=timeout)
        # Could be 400 or possibly 404 if product stock is checked strictly, but per spec 400 expected
        assert r.status_code == 400, f"Expected 400 for excessive quantity but got {r.status_code}"

        # 3d. Error case: unauthenticated access (no Authorization header)
        payload_unauth = {
            "product_id": product_id,
            "quantity": 1
        }
        r = requests.post(f"{BASE_URL}/orders/cart/add_item/", json=payload_unauth, timeout=timeout)
        assert r.status_code == 401, f"Expected 401 for unauthenticated add_item but got {r.status_code}"

    finally:
        # Cleanup user registered for the test: no explicit user deletion endpoint provided.
        # No cart clear endpoint documented; normally would delete user or cart items
        # Skipping explicit cleanup due to lack of API support.
        pass

test_post_api_v1_orders_cart_add_item()