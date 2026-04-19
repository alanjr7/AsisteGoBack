"""Tests para el módulo de solicitudes."""
import pytest


def create_test_cliente(client):
    """Helper para crear cliente de prueba."""
    response = client.post("/clientes/", json={
        "nombre": "Test Cliente",
        "telefono": "+591 7123 4567",
        "email": "test@solicitud.com",
        "lat": -17.7856,
        "lng": -63.1789
    })
    return response.json()["id"]


def test_create_solicitud(client):
    """Test crear solicitud."""
    cliente_id = create_test_cliente(client)
    
    solicitud_data = {
        "cliente_id": cliente_id,
        "vehiculo": {
            "marca": "Toyota",
            "modelo": "Corolla",
            "anio": 2020,
            "placa": "ABC123",
            "color": "Blanco",
            "tipo": "Sedán"
        },
        "descripcion": "Problema con el motor",
        "problema": "El auto no enciende",
        "distancia": 5.0,
        "lat": -17.7856,
        "lng": -63.1789
    }
    
    response = client.post("/solicitudes/", json=solicitud_data)
    assert response.status_code == 200
    data = response.json()
    assert data["descripcion"] == solicitud_data["descripcion"]
    assert data["estado"] == "pendiente"
    assert "id" in data


def test_get_solicitudes(client):
    """Test listar solicitudes."""
    response = client.get("/solicitudes/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_solicitud_by_id(client):
    """Test obtener solicitud por ID."""
    cliente_id = create_test_cliente(client)
    
    # Crear solicitud
    create_response = client.post("/solicitudes/", json={
        "cliente_id": cliente_id,
        "vehiculo": {
            "marca": "Toyota",
            "modelo": "Corolla",
            "anio": 2020,
            "placa": "XYZ789",
            "color": "Blanco",
            "tipo": "Sedán"
        },
        "descripcion": "Problema eléctrico",
        "problema": "No prende las luces",
        "distancia": 3.0,
        "lat": -17.7856,
        "lng": -63.1789
    })
    solicitud_id = create_response.json()["id"]
    
    # Obtener por ID
    response = client.get(f"/solicitudes/{solicitud_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == solicitud_id


def test_update_solicitud_status(client):
    """Test actualizar estado de solicitud."""
    cliente_id = create_test_cliente(client)
    
    # Crear solicitud
    create_response = client.post("/solicitudes/", json={
        "cliente_id": cliente_id,
        "vehiculo": {
            "marca": "Toyota",
            "modelo": "Corolla",
            "anio": 2020,
            "placa": "STATUS1",
            "color": "Rojo",
            "tipo": "Sedán"
        },
        "descripcion": "Test de cambio de estado",
        "problema": "Test",
        "distancia": 2.0,
        "lat": -17.7856,
        "lng": -63.1789
    })
    solicitud_id = create_response.json()["id"]
    
    # Cambiar estado
    response = client.put(f"/solicitudes/{solicitud_id}/estado", json={"estado": "aceptada"})
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "aceptada"


def test_delete_solicitud(client):
    """Test eliminar solicitud."""
    cliente_id = create_test_cliente(client)
    
    # Crear solicitud
    create_response = client.post("/solicitudes/", json={
        "cliente_id": cliente_id,
        "vehiculo": {
            "marca": "Toyota",
            "modelo": "Corolla",
            "anio": 2020,
            "placa": "DELETE1",
            "color": "Azul",
            "tipo": "Sedán"
        },
        "descripcion": "Test de eliminación",
        "problema": "Test",
        "distancia": 1.0,
        "lat": -17.7856,
        "lng": -63.1789
    })
    solicitud_id = create_response.json()["id"]
    
    # Eliminar
    response = client.delete(f"/solicitudes/{solicitud_id}")
    assert response.status_code == 200
    
    # Verificar que ya no existe
    get_response = client.get(f"/solicitudes/{solicitud_id}")
    assert get_response.status_code == 404
