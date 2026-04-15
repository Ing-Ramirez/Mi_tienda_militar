import io
import os
import time
import uuid

import requests

BASE_URL = "http://localhost"
API_PREFIX = "/api/v1"

def test_post_api_v1_orders_checkout():
    session = requests.Session()

    # Register a new user
    email = f"user_{int(time.time())}@test.com"
    password = os.environ.get("TEST_USER_PASSWORD", "Xq7!mZ2#vL9")
    register_data = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password
    }
    register_resp = session.post(
        f"{BASE_URL}{API_PREFIX}/auth/register/",
        json=register_data,
        timeout=30
    )
    assert register_resp.status_code == 201, f"Registration failed: {register_resp.text}"
    token = register_resp.json().get("access")
    assert token, "No access token received on registration"

    headers = {"Authorization": f"Bearer {token}"}

    try:
        # Get products (to have a product to add to cart and to get a real UUID if needed)
        products_resp = session.get(f"{BASE_URL}{API_PREFIX}/products/", timeout=30)
        assert products_resp.status_code == 200, f"Failed to get products: {products_resp.text}"
        products_json = products_resp.json()
        results = products_json.get("results")
        assert results and len(results) > 0, "No products returned"
        product_id = results[0]["id"]
        
        # Add product to cart (required to create an order)
        add_item_payload = {
            "product_id": product_id,
            "quantity": 1,
            "talla": "M",
            "bordado": "Test",
            "rh": "O+"
        }
        add_item_resp = session.post(
            f"{BASE_URL}{API_PREFIX}/orders/cart/add_item/",
            json=add_item_payload,
            headers=headers,
            timeout=30
        )
        assert add_item_resp.status_code == 200, f"Add item failed: {add_item_resp.text}"
        
        # Prepare multipart form data for order checkout with manual Nequi payment
        # Required shipping fields and email plus payment_proof file
        shipping_full_name = "Test User"
        shipping_phone = "+1234567890"
        shipping_department = "Test Dept"
        shipping_city = "Test City"
        shipping_address_line1 = "123 Test Street"
        payment_proof_content = b"dummy file content for testing"
        payment_proof_file = io.BytesIO(payment_proof_content)
        payment_proof_file.name = "proof.jpg"

        valid_data = {
            "shipping_full_name": (None, shipping_full_name),
            "shipping_phone": (None, shipping_phone),
            "shipping_department": (None, shipping_department),
            "shipping_city": (None, shipping_city),
            "shipping_address_line1": (None, shipping_address_line1),
            "email": (None, email),
            "payment_proof": ("proof.jpg", payment_proof_file, "image/jpeg"),
        }

        # Test success case: 201 Order object
        checkout_resp = session.post(
            f"{BASE_URL}{API_PREFIX}/orders/checkout/",
            files=valid_data,
            headers=headers,
            timeout=30
        )
        assert checkout_resp.status_code == 201, f"Order checkout failed: {checkout_resp.text}"
        order_obj = checkout_resp.json()
        assert isinstance(order_obj, dict), "Order object not returned properly"
        assert "id" in order_obj or "order_number" in order_obj, "Order object missing expected fields"

        # Test failure cases: 400 response for missing required fields or missing file
        # Prepare form with missing shipping_full_name and missing payment_proof
        invalid_data_cases = [
            {
                # missing shipping_full_name
                "shipping_phone": (None, shipping_phone),
                "shipping_department": (None, shipping_department),
                "shipping_city": (None, shipping_city),
                "shipping_address_line1": (None, shipping_address_line1),
                "email": (None, email),
                "payment_proof": ("proof.jpg", io.BytesIO(payment_proof_content), "image/jpeg"),
            },
            {
                # missing payment_proof
                "shipping_full_name": (None, shipping_full_name),
                "shipping_phone": (None, shipping_phone),
                "shipping_department": (None, shipping_department),
                "shipping_city": (None, shipping_city),
                "shipping_address_line1": (None, shipping_address_line1),
                "email": (None, email)
            }
        ]

        for invalid_data in invalid_data_cases:
            resp = session.post(
                f"{BASE_URL}{API_PREFIX}/orders/checkout/",
                files=invalid_data,
                headers=headers,
                timeout=30
            )
            assert resp.status_code == 400, f"Expected 400 for invalid data but got {resp.status_code}: {resp.text}"

    finally:
        # Cleanup is typically deleting the created order,
        # but no delete endpoint described in PRD for orders, so no explicit cleanup possible.
        pass

test_post_api_v1_orders_checkout()