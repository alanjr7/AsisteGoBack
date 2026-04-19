"""Configuración de pytest para tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database_sql import Base, get_db
from main import app

# Base de datos en memoria para tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Crear una sesión de base de datos de prueba."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Crear un cliente de test con sesión de BD inyectada."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data():
    """Datos de usuario de ejemplo para tests."""
    return {
        "nombre": "Test User",
        "email": "test@example.com",
        "telefono": "+591 7123 4567",
        "password": "testpassword123"
    }


@pytest.fixture
def sample_cliente_data():
    """Datos de cliente de ejemplo para tests."""
    return {
        "nombre": "Cliente Test",
        "telefono": "+591 7123 4567",
        "email": "cliente@test.com",
        "lat": -17.7856,
        "lng": -63.1789
    }
