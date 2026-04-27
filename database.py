"""
Base de datos en memoria para desarrollo inicial.
En producción, reemplazar con SQLAlchemy y PostgreSQL/MySQL.
"""
from typing import Dict, List, Optional
from datetime import datetime
from utils.timezone import get_now
import uuid


class InMemoryDB:
    """Base de datos en memoria para desarrollo."""
    
    def __init__(self):
        self.clientes: Dict[str, dict] = {}
        self.vehiculos: Dict[str, dict] = {}
        self.solicitudes: Dict[str, dict] = {}
        self.repuestos: Dict[str, dict] = {}
        self.solicitudes_repuesto: Dict[str, dict] = {}
        self.servicios: Dict[str, dict] = {}
        self.notificaciones: Dict[str, dict] = {}
        self.personal: Dict[str, dict] = {}
        self.facturas: Dict[str, dict] = {}
        self.taller: Optional[dict] = None
        self.mensajes_chat: Dict[str, List[dict]] = {}  # solicitud_id -> mensajes
        self.calificaciones: Dict[str, dict] = {}
        self.evidencias: Dict[str, dict] = {}  # NUEVO: Evidencias (fotos, audios)
        self.ubicaciones_grua: Dict[str, dict] = {}  # NUEVO: Ubicaciones de gruistas
        self.comprobantes_pago: Dict[str, dict] = {}  # NUEVO: Comprobantes de pago
        self.users = {
            "admin@asistego.com": {"password": "admin123", "rol": "administrador"},
            "taller@demo.com": {"password": "demo123", "rol": "encargado"},
        }
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Inicializar datos de prueba."""
        # Clientes
        clientes_mock = [
            {"id": "1", "nombre": "Carlos Mendoza", "telefono": "+591 7123 4567", 
             "foto": "https://i.pravatar.cc/150?img=12", "lat": -17.7856, "lng": -63.1789},
            {"id": "2", "nombre": "María González", "telefono": "+591 7234 5678",
             "foto": "https://i.pravatar.cc/150?img=5", "lat": -17.7801, "lng": -63.1845},
            {"id": "3", "nombre": "Jorge Ramírez", "telefono": "+591 7345 6789",
             "foto": "https://i.pravatar.cc/150?img=8", "lat": -17.7890, "lng": -63.1756},
            {"id": "4", "nombre": "Ana Flores", "telefono": "+591 7456 7890",
             "foto": "https://i.pravatar.cc/150?img=9", "lat": -17.7767, "lng": -63.1902},
        ]
        for c in clientes_mock:
            self.clientes[c["id"]] = c
        
        # Personal
        personal_mock = [
            {"id": "p1", "nombre": "José Martínez", "rol": "mecanico", "estado": "disponible",
             "foto": "https://i.pravatar.cc/150?img=13", "telefono": "+591 7111 2222", 
             "asistencias_dia": 3, "asistencias_mes": 45},
            {"id": "p2", "nombre": "Alexis Rojas", "rol": "electrico", "estado": "en_camino",
             "foto": "https://i.pravatar.cc/150?img=14", "telefono": "+591 7222 3333",
             "asistencias_dia": 2, "asistencias_mes": 38},
            {"id": "p3", "nombre": "Mario Sánchez", "rol": "grua", "estado": "regresando",
             "foto": "https://i.pravatar.cc/150?img=15", "telefono": "+591 7333 4444",
             "asistencias_dia": 1, "asistencias_mes": 22},
            {"id": "p4", "nombre": "Oscar López", "rol": "mecanico", "estado": "ocupado",
             "foto": "https://i.pravatar.cc/150?img=16", "telefono": "+591 7444 5555",
             "asistencias_dia": 4, "asistencias_mes": 52},
        ]
        for p in personal_mock:
            self.personal[p["id"]] = p
        
        # Repuestos
        repuestos_mock = [
            {"id": "r1", "nombre": "Batería 12V 60Ah", "descripcion": "Batería de alta calidad",
             "precio": 450, "imagen": "https://images.unsplash.com/photo-1609412825868-0d4c9c5c0f3e?w=300",
             "disponible": True, "marca": "Bosch", "categoria": "Sistema Eléctrico",
             "vehiculos_compatibles": ["Toyota Corolla", "Honda Civic"]},
            {"id": "r2", "nombre": "Pastillas de Freno", "descripcion": "Pastillas cerámicas",
             "precio": 280, "imagen": "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=300",
             "disponible": True, "marca": "Brembo", "categoria": "Sistema de Frenos",
             "vehiculos_compatibles": ["Honda Civic", "Toyota Corolla"]},
            {"id": "r3", "nombre": "Aceite Sintético 5W-30", "descripcion": "Aceite sintético",
             "precio": 120, "imagen": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=300",
             "disponible": True, "marca": "Castrol", "categoria": "Lubricantes",
             "vehiculos_compatibles": ["Todos"]},
        ]
        for r in repuestos_mock:
            self.repuestos[r["id"]] = r
        
        # Taller
        self.taller = {
            "id": "t1",
            "nombre": "Taller AsisteGO",
            "foto": "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=400",
            "ubicacion": "Av. Cristo Redentor, Santa Cruz, Bolivia",
            "telefono": "+591 3 123 4567",
            "email": "contacto@asistego.com",
            "calificacion": 4.8,
            "total_servicios": 1247,
            "descripcion": "Taller mecánico especializado en asistencia móvil 24/7"
        }
        
        # Notificaciones
        notif_mock = [
            {"id": "n1", "tipo": "solicitud", "titulo": "Nueva solicitud", 
             "mensaje": "Carlos Mendoza necesita asistencia", "leida": False,
             "timestamp": get_now().isoformat()},
        ]
        for n in notif_mock:
            self.notificaciones[n["id"]] = n
    
    def generate_id(self) -> str:
        """Generar ID único."""
        return str(uuid.uuid4())
    
    def get_all(self, table: str) -> List[dict]:
        """Obtener todos los registros de una tabla."""
        db_table = getattr(self, table, {})
        if isinstance(db_table, dict):
            return list(db_table.values())
        return []
    
    def get_by_id(self, table: str, id: str) -> Optional[dict]:
        """Obtener registro por ID."""
        db_table = getattr(self, table, {})
        if isinstance(db_table, dict):
            return db_table.get(id)
        return None
    
    def create(self, table: str, data: dict) -> dict:
        """Crear nuevo registro."""
        if "id" not in data:
            data["id"] = self.generate_id()
        if "timestamp" not in data and table != "clientes":
            data["timestamp"] = get_now().isoformat()
        
        db_table = getattr(self, table)
        if isinstance(db_table, dict):
            db_table[data["id"]] = data
        return data
    
    def update(self, table: str, id: str, data: dict) -> Optional[dict]:
        """Actualizar registro."""
        db_table = getattr(self, table, {})
        if isinstance(db_table, dict) and id in db_table:
            db_table[id].update(data)
            return db_table[id]
        return None
    
    def delete(self, table: str, id: str) -> bool:
        """Eliminar registro."""
        db_table = getattr(self, table, {})
        if isinstance(db_table, dict) and id in db_table:
            del db_table[id]
            return True
        return False


# Instancia global de la base de datos
db = InMemoryDB()
