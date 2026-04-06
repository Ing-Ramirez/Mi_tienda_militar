import requests
import time

BASE_URL = "http://localhost:80/api/v1/products/"
TIMEOUT = 30

def test_get_api_v1_products():
    session = requests.Session()
    params_list = [
        {},  # no filters
        {"category": None},  # no category filter (will skip None)
        {"status": "active"},
        {"status": "inactive"},
        {"is_featured": "true"},
        {"is_featured": "false"},
        {"is_new": "true"},
        {"is_new": "false"},
        {"search": "tactical"},
        {"category": None, "status": "active", "is_featured": "true", "is_new": "false", "search": "rifle"}
    ]

    # First, get categories to fetch a real category uuid for filtering (optional)
    try:
        cat_resp = session.get(BASE_URL + "categories/", timeout=TIMEOUT)
        category_uuid = None
        if cat_resp.status_code == 200:
            cats = cat_resp.json()
            if isinstance(cats, list) and len(cats) > 0:
                category_uuid = cats[0].get("id")
    except Exception:
        category_uuid = None

    # Prepare filters, replacing None with actual category uuid if possible
    test_params = []
    for p in params_list:
        new_p = {}
        for k,v in p.items():
            if v is None and k == "category" and category_uuid:
                new_p[k] = category_uuid
            elif v is not None:
                new_p[k] = v
        test_params.append(new_p)

    for params in test_params:
        try:
            response = session.get(BASE_URL, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            assert False, f"Request failed: {e}"

        assert response.status_code == 200, f"Expected status 200, got {response.status_code} for params {params}"
        try:
            data = response.json()
        except Exception:
            assert False, f"Response is not valid JSON for params {params}"

        # Validate paginated structure: must have keys like count, next, previous, results
        assert isinstance(data, dict), f"Response JSON should be an object for params {params}"
        required_keys = {"count", "next", "previous", "results"}
        assert required_keys.issubset(data.keys()), f"Missing pagination keys in response for params {params}"

        # results should be a list of products
        results = data.get("results")
        assert isinstance(results, list), f"'results' should be a list for params {params}"

        # If results not empty, check basic keys in first product
        if results:
            product = results[0]
            # Common product keys to check presence
            assert "id" in product, f"Product missing 'id' for params {params}"
            assert "sku" in product or "slug" in product or "name" in product, f"Product missing identifying fields for params {params}"

            # Optional: if filtering by status provided verify all statuses match that filter (if status in filter)
            if "status" in params:
                status_filter = params["status"]
                # product could have 'status' field
                if "status" in product:
                    assert product["status"] == status_filter, f"Product status {product['status']} does not match filter {status_filter}"

            # If filtering by is_featured or is_new, check those boolean fields
            if "is_featured" in params:
                val = params["is_featured"].lower() == "true"
                if "is_featured" in product:
                    assert product["is_featured"] == val, f"Product is_featured {product['is_featured']} does not match filter {val}"
            if "is_new" in params:
                val = params["is_new"].lower() == "true"
                if "is_new" in product:
                    assert product["is_new"] == val, f"Product is_new {product['is_new']} does not match filter {val}"

    session.close()

test_get_api_v1_products()