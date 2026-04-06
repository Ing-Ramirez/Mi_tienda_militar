import requests
from urllib.parse import urljoin

BASE_URL = "http://localhost:80/api/v1/"
TIMEOUT = 30


def test_get_api_v1_products():
    """
    Test product listing endpoint with pagination and optional filters:
    category (uuid), status (active|inactive), is_featured (bool),
    is_new (bool), and search (string).
    Verify correct paginated product list is returned and response schema.
    """
    endpoint = urljoin(BASE_URL, "products/")
    params_list = [
        {},  # No filters
        {"status": "active"},
        {"status": "inactive"},
        {"is_featured": "true"},
        {"is_featured": "false"},
        {"is_new": "true"},
        {"is_new": "false"},
        {"search": "tactical"},
    ]

    # Attempt to retrieve categories if any to test category filter
    categories_url = urljoin(BASE_URL, "products/categories/")
    category_ids = []
    try:
        resp_cats = requests.get(categories_url, timeout=TIMEOUT)
        assert resp_cats.status_code == 200, f"Failed to get categories: {resp_cats.text}"
        cats_data = resp_cats.json()
        if isinstance(cats_data, list) and len(cats_data) > 0:
            # Collect up to first 2 category ids for testing filter
            category_ids = [cat.get("id") for cat in cats_data if "id" in cat][:2]
    except Exception:
        # If fails, no category filter test will be done
        category_ids = []

    if category_ids:
        params_list.append({"category": category_ids[0]})
        # Test with second category if exists
        if len(category_ids) > 1:
            params_list.append({"category": category_ids[1]})

    for params in params_list:
        resp = requests.get(endpoint, params=params, timeout=TIMEOUT)
        assert resp.status_code == 200, f"Failed for params {params}: {resp.text}"
        data = resp.json()

        # Validate basic pagination keys
        assert isinstance(data, dict), "Response is not a JSON object"
        expected_keys = {"count", "next", "previous", "results"}
        assert expected_keys.issubset(data.keys()), f"Pagination keys missing in response for params {params}"
        # Validate results is a list of products with expected keys
        results = data.get("results")
        assert isinstance(results, list), f"'results' is not a list for params {params}"
        # If results are not empty, check product fields
        if results:
            product = results[0]
            # Minimal expected product keys (based on product example in PRD)
            product_expected_keys = {"id", "sku", "name", "slug"}
            assert product_expected_keys.issubset(product.keys()), f"Product keys missing for params {params}"

    # Additional combined filter test
    combined_params = {
        "status": "active",
        "is_featured": "true",
        "is_new": "true",
        "search": "military"
    }
    if category_ids:
        combined_params["category"] = category_ids[0]

    resp = requests.get(endpoint, params=combined_params, timeout=TIMEOUT)
    assert resp.status_code == 200, f"Failed combined filters test: {resp.text}"
    data = resp.json()
    assert "results" in data and isinstance(data["results"], list), "Invalid results in combined filter response"


test_get_api_v1_products()