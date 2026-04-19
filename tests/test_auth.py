"""Tests para el módulo de autenticación."""
import pytest


def test_register_user(client, sample_user_data):
    """Test registro de usuario nuevo."""
    response = client.post("/auth/register", json=sample_user_data)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == sample_user_data["email"]
    assert "id" in data
    assert "password" not in data  # No debe retornar password


def test_register_duplicate_email(client, sample_user_data):
    """Test que no permite emails duplicados."""
    # Crear primer usuario
    response1 = client.post("/auth/register", json=sample_user_data)
    assert response1.status_code == 200
    
    # Intentar crear segundo usuario con mismo email
    response2 = client.post("/auth/register", json=sample_user_data)
    assert response2.status_code == 400
    assert "ya existe" in response2.json()["detail"].lower()


def test_login_success(client, sample_user_data):
    """Test login exitoso."""
    # Registrar usuario primero
    client.post("/auth/register", json=sample_user_data)
    
    # Login
    login_data = {
        "username": sample_user_data["email"],
        "password": sample_user_data["password"]
    }
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client, sample_user_data):
    """Test login con credenciales inválidas."""
    login_data = {
        "username": sample_user_data["email"],
        "password": "wrongpassword"
    }
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 401


def test_get_current_user(client, sample_user_data):
    """Test obtener usuario actual con token."""
    # Registrar y login
    client.post("/auth/register", json=sample_user_data)
    login_response = client.post("/auth/login", data={
        "username": sample_user_data["email"],
        "password": sample_user_data["password"]
    })
    token = login_response.json()["access_token"]
    
    # Obtener usuario actual
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == sample_user_data["email"]


def test_get_current_user_no_token(client):
    """Test que requiere token para obtener usuario actual."""
    response = client.get("/auth/me")
    assert response.status_code == 401
