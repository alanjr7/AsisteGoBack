"""Tests para el módulo de clientes."""
import pytest


def test_create_cliente(client):
    """Test crear cliente."""
    cliente_data = {
        "nombre": "Carlos Mendoza",
        "telefono": "+591 7123 4567",
        "email": "carlos@test.com",
        "lat": -17.7856,
        "lng": -63.1789
    }
    response = client.post("/clientes/", json=cliente_data)
    assert response.status_code == 200
    data = response.json()
    assert data["nombre"] == cliente_data["nombre"]
    assert "id" in data


def test_get_clientes(client):
    """Test listar clientes."""
    # Crear cliente primero
    client.post("/clientes/", json={
        "nombre": "Test Cliente",
        "telefono": "+591 7123 4567",
        "email": "test@cliente.com",
        "lat": -17.7856,
        "lng": -63.1789
    })
    
    response = client.get("/clientes/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_cliente_by_id(client):
    """Test obtener cliente por ID."""
    # Crear cliente
    create_response = client.post("/clientes/", json={
        "nombre": "Test Cliente",
        "telefono": "+591 7123 4567",
        "email": "test2@cliente.com",
        "lat": -17.7856,
        "lng": -63.1789
    })
    cliente_id = create_response.json()["id"]
    
    # Obtener por ID
    response = client.get(f"/clientes/{cliente_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cliente_id


def test_update_cliente(client):
    """Test actualizar cliente."""
    # Crear cliente
    create_response = client.post("/clientes/", json={
        "nombre": "Test Original",
        "telefono": "+591 7123 4567",
        "email": "original@test.com",
        "lat": -17.7856,
        "lng": -63.1789
    })
    cliente_id = create_response.json()["id"]
    
    # Actualizar
    update_data = {"nombre": "Test Actualizado"}
    response = client.put(f"/clientes/{cliente_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["nombre"] == "Test Actualizado"


def test_delete_cliente(client):
    """Test eliminar cliente."""
    # Crear cliente
    create_response = client.post("/clientes/", json={
        "nombre": "Test Delete",
        "telefono": "+591 7123 4567",
        "email": "delete@test.com",
        "lat": -17.7856,
        "lng": -63.1789
    })
    cliente_id = create_response.json()["id"]
    
    # Eliminar
    response = client.delete(f"/clientes/{cliente_id}")
    assert response.status_code == 200
    
    # Verificar que ya no existe
    get_response = client.get(f"/clientes/{cliente_id}")
    assert get_response.status_code == 404
