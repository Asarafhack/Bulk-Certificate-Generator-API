def test_swagger_and_openapi_include_the_api_contract(client):
    docs = client.get("/docs")
    openapi = client.get("/openapi.json")
    specification = openapi.json()

    assert docs.status_code == 200
    assert "swagger-ui" in docs.text.lower()
    assert openapi.status_code == 200
    assert specification["info"]["title"] == "Bulk Certificate Generator API"
    assert "/health" in specification["paths"]
    assert "/api/v1/jobs" in specification["paths"]
    assert "202" in specification["paths"]["/api/v1/jobs"]["post"]["responses"]
    assert "/api/v1/certificates/{certificate_id}" in specification["paths"]
