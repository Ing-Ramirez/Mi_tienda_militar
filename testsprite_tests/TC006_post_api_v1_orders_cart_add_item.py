import requests
import uuid
import time

BASE_URL = "http://localhost:80/api/v1"
PASSWORD = "Xq7!mZ2#vL9"

def test_post_api_v1_orders_cart_add_item():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    timeout = 30

    # Generate unique email for registration
    timestamp = int(time.time() * 1000)
    email = f"user_{timestamp}@test.com"
    register_url = f"{BASE_URL}/auth/register/"
    register_data = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": PASSWORD,
        "password2": PASSWORD
    }

    # Register user
    resp = session.post(register_url, json=register_data, timeout=timeout)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    resp_json = resp.json()
    access_token = resp_json.get("access")
    assert access_token, "No access token in registration response"
    # Save access token for auth
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    # FETCH valid product_id from products list
    products_url = f"{BASE_URL}/products/"
    resp = session.get(products_url, timeout=timeout)
    assert resp.status_code == 200, f"Could not fetch products: {resp.text}"
    products_data = resp.json()
    results = products_data.get("results")
    assert results and isinstance(results, list), "Products list is empty or invalid"
    valid_product_id = results[0].get("id")
    assert valid_product_id, "Valid product id missing from product results"

    add_item_url = f"{BASE_URL}/orders/cart/add_item/"

    # Success case: valid product_id, quantity, optional customization fields
    valid_payload = {
        "product_id": valid_product_id,
        "quantity": 2,
        "talla": "M",
        "bordado": "Name",
        "rh": "O+"
    }
    resp = session.post(add_item_url, json=valid_payload, timeout=timeout)
    assert resp.status_code == 201, f"Adding valid item failed: {resp.text}"
    cart = resp.json()
    assert isinstance(cart, dict), "Cart response is not a dict"
    # Basic validations for full Cart object
    assert "items" in cart and isinstance(cart["items"], list), "Cart missing items list"
    assert any(item.get("product") == valid_product_id for item in cart["items"]), "Cart items missing added product"
    assert "total_items" in cart, "Cart missing total_items"
    assert "subtotal" in cart, "Cart missing subtotal"
    assert "updated_at" in cart, "Cart missing updated_at"

    # 404 case: invalid product_id
    invalid_product_id = str(uuid.uuid4())
    invalid_payload = {
        "product_id": invalid_product_id,
        "quantity": 1
    }
    resp = session.post(add_item_url, json=invalid_payload, timeout=timeout)
    assert resp.status_code == 404, f"Expected 404 for invalid product_id, got {resp.status_code}"

    # 400 case: invalid quantity (0)
    invalid_qty_payload = {
        "product_id": valid_product_id,
        "quantity": 0
    }
    resp = session.post(add_item_url, json=invalid_qty_payload, timeout=timeout)
    assert resp.status_code == 400, f"Expected 400 for invalid quantity, got {resp.status_code}"

test_post_api_v1_orders_cart_add_item()