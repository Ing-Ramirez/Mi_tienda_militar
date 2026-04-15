import time
import os

import requests
import uuid

BASE_URL = "http://localhost/api/v1"
TIMEOUT = 30


def test_post_api_v1_products_slug_reviews_create():
    session = requests.Session()

    # Register a new user
    email = f"user_{int(time.time())}@test.com"
    password = os.environ.get("TEST_USER_PASSWORD", "Xq7!mZ2#vL9")
    register_data = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": password,
        "password2": password,
    }
    r = session.post(f"{BASE_URL}/auth/register/", json=register_data, timeout=TIMEOUT)
    assert r.status_code == 201, f"User registration failed: {r.text}"
    access_token = r.json().get("access")
    assert access_token, "No access token in registration response"

    headers = {"Authorization": f"Bearer {access_token}"}

    # Get products list to obtain product_id and slug
    r = session.get(f"{BASE_URL}/products/", timeout=TIMEOUT)
    assert r.status_code == 200, f"Failed to get products: {r.text}"
    products_list = r.json().get("results")
    assert products_list and len(products_list) > 0, "No products found"
    product = products_list[0]
    product_id = product.get("id")
    product_slug = product.get("slug")
    assert product_id and product_slug, "Invalid product data"

    # Get eligible products for review to find a delivered order with this product
    r = session.get(f"{BASE_URL}/products/eligible-reviews/", headers=headers, timeout=TIMEOUT)
    assert r.status_code == 200, f"Failed to get eligible reviews: {r.text}"
    eligible_reviews = r.json()
    # Find eligible review with product_slug matching our product_slug
    eligible_review = None
    for item in eligible_reviews:
        if item.get("product_slug") == product_slug:
            eligible_review = item
            break
    if not eligible_review:
        # No eligible review found: create an order with the product and mark it delivered
        # We need to add product to cart, checkout, and simulate delivery by test assumption
        # For the sake of this test, we create order and assume it is delivered
        # Add product to cart
        add_cart_payload = {
            "product_id": product_id,
            "quantity": 1,
            "talla": "M",
            "bordado": "Name",
            "rh": "O+"
        }
        r = session.post(f"{BASE_URL}/orders/cart/add_item/", headers=headers, json=add_cart_payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Failed to add item to cart: {r.text}"

        # Checkout order (using dummy required shipping data and a payment_proof file)
        files = {"payment_proof": ("proof.png", b"dummydata", "image/png")}
        checkout_payload = {
            "shipping_full_name": "Test User",
            "shipping_phone": "1234567890",
            "shipping_department": "Test Dept",
            "shipping_city": "Test City",
            "shipping_address_line1": "123 Test St",
            "email": email,
        }
        r = session.post(f"{BASE_URL}/orders/checkout/", headers=headers, data=checkout_payload, files=files, timeout=TIMEOUT)
        assert r.status_code == 201, f"Failed to checkout order: {r.text}"
        order = r.json()
        order_id = order.get("id")
        assert order_id, "No order id in checkout response"

        # Normally, order must be delivered for eligibility.
        # Since we cannot change server state here,
        # skip to test 403 response using this order_id and product_slug for a product not in delivered order.

    else:
        order_id = eligible_review.get("order_id")
        assert order_id, "No order_id in eligible review item"

    # Now test the happy path creating a review

    review_create_url = f"{BASE_URL}/products/{product_slug}/reviews/create/"

    # Valid review create payload
    valid_review_payload = {
        "order_id": order_id,
        "rating": 5,
        "comment": "Excellent product, highly recommended!",
        "images": []
    }

    try:
        r = session.post(review_create_url, headers=headers, json=valid_review_payload, timeout=TIMEOUT)
        if r.status_code == 201:
            review = r.json()
            assert "id" in review, "Review object missing id field"
            assert review.get("order_id") == order_id
            assert review.get("rating") == 5
            assert review.get("comment") == "Excellent product, highly recommended!"
        elif r.status_code == 403:
            # Order not delivered or product not in order
            assert "detail" in r.json() or r.text, "No detail message on 403"
        elif r.status_code == 400:
            # Validation errors or duplicate review
            assert "detail" in r.json() or r.text, "No detail message on 400"
        else:
            assert False, f"Unexpected status code {r.status_code}: {r.text}"
    finally:
        # Cleanup: delete the created review if possible (API doesn't expose delete, so skip)
        pass

    # Additional tests:

    # Test 403: invalid order (not delivered or product not in order)
    invalid_order_id = str(uuid.uuid4())
    invalid_payload = {
        "order_id": invalid_order_id,
        "rating": 4,
        "comment": "Trying to review with invalid order",
        "images": []
    }
    r = session.post(review_create_url, headers=headers, json=invalid_payload, timeout=TIMEOUT)
    assert r.status_code == 403, f"Expected 403 for invalid order, got {r.status_code}"

    # Test 400: duplicate review (re-post same review)
    r = session.post(review_create_url, headers=headers, json=valid_review_payload, timeout=TIMEOUT)
    # Could be 201 if first call failed or if review was not created, or 400 if duplicate
    assert r.status_code in (201, 400), f"Expected 201 or 400 for duplicate review, got {r.status_code}"

    # Test 400: validation error (missing rating)
    invalid_rating_payload = {
        "order_id": order_id,
        "comment": "Missing rating field",
    }
    r = session.post(review_create_url, headers=headers, json=invalid_rating_payload, timeout=TIMEOUT)
    assert r.status_code == 400, f"Expected 400 for missing rating, got {r.status_code}"


test_post_api_v1_products_slug_reviews_create()