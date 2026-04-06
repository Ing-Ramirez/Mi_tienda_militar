import requests
import uuid
import time
from io import BytesIO

BASE_URL = "http://localhost:80/api/v1"
TIMEOUT = 30
PASSWORD = "Xq7!mZ2#vL9"


def test_post_api_v1_orders_checkout():
    session = requests.Session()
    timestamp = str(int(time.time() * 1000))
    email = f"user_{timestamp}@test.com"
    register_url = f"{BASE_URL}/auth/register/"
    login_url = f"{BASE_URL}/auth/login/"
    products_url = f"{BASE_URL}/products/"
    add_item_url = f"{BASE_URL}/orders/cart/add_item/"
    checkout_url = f"{BASE_URL}/orders/checkout/"

    # Register user
    register_payload = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": PASSWORD,
        "password2": PASSWORD,
    }
    resp = session.post(register_url, json=register_payload, timeout=TIMEOUT)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    access_token = resp.json().get("access")
    assert access_token and isinstance(access_token, str)

    headers_auth = {"Authorization": f"Bearer {access_token}"}

    # Login user to get fresh token and set refresh token cookie in session if needed
    login_payload = {"email": email, "password": PASSWORD}
    resp = session.post(login_url, json=login_payload, timeout=TIMEOUT)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    access_token = resp.json().get("access")
    assert access_token and isinstance(access_token, str)
    headers_auth = {"Authorization": f"Bearer {access_token}"}

    # Get products list to obtain a valid product_id
    resp = session.get(products_url, timeout=TIMEOUT)
    assert resp.status_code == 200, f"Get products failed: {resp.text}"
    data = resp.json()
    results = data.get("results")
    assert results and isinstance(results, list), "Products results missing or invalid"
    product_id = results[0].get("id")
    assert product_id and isinstance(product_id, str)

    # Add item to cart
    add_item_payload = {
        "product_id": product_id,
        "quantity": 1,
        "talla": "M",
        "bordado": "text",
        "rh": "O+",
    }
    resp = session.post(add_item_url, json=add_item_payload, headers=headers_auth, timeout=TIMEOUT)
    assert resp.status_code == 201, f"Add item to cart failed: {resp.text}"
    cart_data = resp.json()
    assert "items" in cart_data and isinstance(cart_data["items"], list)
    assert any(item.get("product") == product_id for item in cart_data["items"])

    # Prepare multipart form data for checkout
    # Required fields: shipping_full_name, shipping_phone, shipping_department,
    # shipping_city, shipping_address_line1, email, payment_proof (file).
    shipping_data = {
        "shipping_full_name": "Test User",
        "shipping_phone": "+571234567890",
        "shipping_department": "Cundinamarca",
        "shipping_city": "Bogotá",
        "shipping_address_line1": "123 Test Street",
        "email": email,
    }
    # Create a minimal valid JPEG image file in memory (1x1 pixel)
    payment_proof_content = (
        b'\xff\xd8\xff\xdb\x00C\x00' + b'\x08' * 64 +
        b'\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01"\x00\x02\x11\x01\x03\x11\x01'
        b'\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xd2\xcf \xff\xd9'
    )
    payment_proof_file = BytesIO(payment_proof_content)
    payment_proof_file.name = "payment_proof.jpg"

    files = {
        "payment_proof": (payment_proof_file.name, payment_proof_file, "image/jpeg"),
    }

    def do_checkout(data_fields, files_data, auth_headers):
        return session.post(
            checkout_url,
            data=data_fields,
            files=files_data,
            headers=auth_headers,
            timeout=TIMEOUT,
        )

    order_id = None
    try:
        # 1) Successful checkout
        resp = do_checkout(shipping_data, files, headers_auth)
        assert resp.status_code == 201, f"Checkout failed: {resp.text}"
        order_obj = resp.json()
        assert isinstance(order_obj, dict)
        assert "id" in order_obj and isinstance(order_obj["id"], str)
        assert "order_number" in order_obj and isinstance(order_obj["order_number"], str)
        order_id = order_obj["id"]

        # 2) Checkout missing required field(s) (e.g., no payment_proof file)
        invalid_data = shipping_data.copy()
        # no payment_proof file
        resp = do_checkout(invalid_data, files_data=None, auth_headers=headers_auth)
        assert resp.status_code == 400, f"Expected 400 for missing payment_proof, got {resp.status_code}"
        err_json = resp.json()
        assert isinstance(err_json, dict)
        # Check validation error keys (generally payment_proof)
        assert any(key in err_json for key in ["payment_proof", "non_field_errors"]) or len(err_json) > 0

        # 3) Checkout with no authentication header -> 401 Unauthorized
        resp = do_checkout(shipping_data, files, auth_headers={})
        assert resp.status_code == 401, f"Expected 401 for no auth, got {resp.status_code}"

    finally:
        # Cleanup: No endpoint for deleting order stated in PRD; skip cleanup or add if needed
        pass


test_post_api_v1_orders_checkout()