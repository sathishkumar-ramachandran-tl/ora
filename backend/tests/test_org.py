def test_create_organization(client):
    """Test creating a new organization"""
    # Mock Auth
    headers = {"Authorization": "Bearer test_token"} 
    # In real test, generate valid token
    
    response = client.post('/api/v2/orgs/', json={
        "name": "Acme Corp",
        "domain": "acme.com"
    }, headers=headers)
    
    # assert response.status_code == 201
    
# Add more tests here
