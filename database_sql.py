"""Conexión SQLAlchemy para MySQL - autenticación, clientes y solicitudes."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from dotenv import load_dotenv
import os
import enum

load_dotenv()

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://asistego_user:asistego123@localhost:3306/asistego_db")

# Crear engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Enums
class EstadoSolicitud(str, enum.Enum):
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    EN_CAMINO = "en_camino"
    REPARANDO = "reparando"
    FINALIZADA = "finalizada"
    RECHAZADA = "rechazada"
    CANCELADA = "cancelada"


class TipoSolicitud(str, enum.Enum):
    NORMAL = "normal"
    GRUA = "grua"


class Cliente(Base):
    """Modelo de cliente en MySQL."""
    __tablename__ = "clientes"

    id = Column(String(36), primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    telefono = Column(String(50), nullable=False)
    email = Column(String(255), nullable=True)
    foto = Column(String(500), nullable=True)
    lat = Column(Float, default=0.0)
    lng = Column(Float, default=0.0)
    veces_atendido = Column(Integer, default=0)
    calificacion_promedio = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Solicitud(Base):
    """Modelo de solicitud en MySQL."""
    __tablename__ = "solicitudes"

    id = Column(String(36), primary_key=True, index=True)
    cliente_id = Column(String(36), ForeignKey("clientes.id"), nullable=False)

    # Vehículo (inline)
    vehiculo_marca = Column(String(100), nullable=False)
    vehiculo_modelo = Column(String(100), nullable=False)
    vehiculo_anio = Column(Integer, nullable=False)
    vehiculo_placa = Column(String(20), nullable=False)
    vehiculo_color = Column(String(50), nullable=False)
    vehiculo_tipo = Column(String(50), default="Sedán")

    # Datos de la solicitud
    descripcion = Column(Text, nullable=False)
    problema = Column(String(255), nullable=False)
    distancia = Column(Float, default=0.0)
    estado = Column(Enum(EstadoSolicitud), default=EstadoSolicitud.PENDIENTE)
    requiere_repuestos = Column(Boolean, default=False)
    tipo = Column(Enum(TipoSolicitud), default=TipoSolicitud.NORMAL)
    
    # Estado de pago
    estado_pago = Column(String(20), default="pendiente")  # pendiente, confirmado, completado, cancelado
    monto_pago = Column(Float, nullable=True)

    # Multimedia
    imagenes = Column(Text, default="[]")  # JSON como string
    audio = Column(String(500), nullable=True)

    # Asignación
    mecanico_asignado_id = Column(String(36), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación
    cliente = relationship("Cliente")


class User(Base):
    """Modelo de usuario en MySQL."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    nombre = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(50), default="encargado")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Factura(Base):
    """Modelo de factura/pago en MySQL."""
    __tablename__ = "facturas"
    
    id = Column(String(36), primary_key=True, index=True)
    solicitud_id = Column(String(36), ForeignKey("solicitudes.id"), nullable=False)
    cliente_id = Column(String(36), ForeignKey("clientes.id"), nullable=False)
    
    # Datos del pago
    monto = Column(Float, nullable=False)
    comision = Column(Float, default=0.0)
    total = Column(Float, nullable=False)
    metodo_pago = Column(String(20), nullable=False)  # qr, tarjeta, efectivo
    
    # Comprobante y estado
    comprobante = Column(String(500), nullable=True)
    enviada = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    cliente = relationship("Cliente")
    solicitud = relationship("Solicitud")


class Personal(Base):
    """Modelo de personal del taller en MySQL."""
    __tablename__ = "personal"
    
    id = Column(String(36), primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    rol = Column(String(50), nullable=False)  # mecanico, electrico, grua, administrador, encargado
    estado = Column(String(50), default="disponible")  # disponible, ocupado, en_camino, regresando
    foto = Column(String(500), nullable=True)
    telefono = Column(String(50), nullable=True)
    asistencias_dia = Column(Integer, default=0)
    asistencias_mes = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SolicitudPersonal(Base):
    """Tabla intermedia para asignar personal a solicitudes."""
    __tablename__ = "solicitud_personal"
    
    id = Column(String(36), primary_key=True, index=True)
    solicitud_id = Column(String(36), ForeignKey("solicitudes.id"), nullable=False)
    personal_id = Column(String(36), ForeignKey("personal.id"), nullable=False)
    rol_asignado = Column(String(50), nullable=False)
    fecha_asignacion = Column(DateTime, default=datetime.utcnow)
    fecha_liberacion = Column(DateTime, nullable=True)
    
    # Relaciones
    solicitud = relationship("Solicitud")
    personal = relationship("Personal")


def get_db():
    """Generador de sesiones de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Crear todas las tablas."""
    Base.metadata.create_all(bind=engine)


def init_mock_data():
    """Inicializar datos de prueba en MySQL."""
    db = SessionLocal()
    try:
        # Verificar si ya hay clientes
        existing = db.query(Cliente).first()
        if existing:
            return  # Datos ya inicializados

        # Crear clientes de prueba
        from uuid import uuid4
        clientes_mock = [
            Cliente(
                id=str(uuid4()),
                nombre="Carlos Mendoza",
                telefono="+591 7123 4567",
                email="carlos@demo.com",
                foto="https://i.pravatar.cc/150?img=12",
                lat=-17.7856,
                lng=-63.1789,
                veces_atendido=0,
            ),
            Cliente(
                id=str(uuid4()),
                nombre="María González",
                telefono="+591 7234 5678",
                email="maria@demo.com",
                foto="https://i.pravatar.cc/150?img=5",
                lat=-17.7801,
                lng=-63.1845,
                veces_atendido=0,
            ),
        ]
        for c in clientes_mock:
            db.add(c)

        # Crear personal de prueba
        personal_mock = [
            Personal(
                id=str(uuid4()),
                nombre="José Martínez",
                rol="mecanico",
                estado="disponible",
                foto="https://i.pravatar.cc/150?img=13",
                telefono="+591 7111 2222",
                asistencias_dia=3,
                asistencias_mes=45,
            ),
            Personal(
                id=str(uuid4()),
                nombre="Alexis Rojas",
                rol="electrico",
                estado="disponible",
                foto="https://i.pravatar.cc/150?img=14",
                telefono="+591 7222 3333",
                asistencias_dia=2,
                asistencias_mes=38,
            ),
            Personal(
                id=str(uuid4()),
                nombre="Mario Sánchez",
                rol="grua",
                estado="disponible",
                foto="https://i.pravatar.cc/150?img=15",
                telefono="+591 7333 4444",
                asistencias_dia=1,
                asistencias_mes=22,
            ),
            Personal(
                id=str(uuid4()),
                nombre="Oscar López",
                rol="mecanico",
                estado="disponible",
                foto="https://i.pravatar.cc/150?img=16",
                telefono="+591 7444 5555",
                asistencias_dia=4,
                asistencias_mes=52,
            ),
        ]
        for p in personal_mock:
            db.add(p)

        db.commit()
        print("✅ Datos de prueba creados en MySQL")
    except Exception as e:
        print(f"⚠️ Error creando datos de prueba: {e}")
        db.rollback()
    finally:
        db.close()
