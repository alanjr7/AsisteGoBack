"""Conexión SQLAlchemy para PostgreSQL - autenticación, clientes y solicitudes."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from utils.timezone import get_now
from dotenv import load_dotenv
import os
import enum

# Cargar .env solo si no existe la variable en el entorno (no sobreescribir Render)
load_dotenv(override=False)

# Configuración de la base de datos
def get_database_url():
    """Obtener y procesar la URL de base de datos."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./asistego.db")
    
    # Log para debugging (ocultar password)
    if database_url and "://" in database_url:
        masked_url = database_url.split("://")[0] + "://***@***" + database_url.rsplit("@", 1)[1] if "@" in database_url else database_url
        print(f"[DATABASE] DATABASE_URL detectada: {masked_url}")
    else:
        print(f"[DATABASE] DATABASE_URL no encontrada, usando default: {database_url}")
    
    # Render usa 'postgres://' o 'postgresql://' pero SQLAlchemy necesita 'postgresql+psycopg2://'
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    return database_url

DATABASE_URL = get_database_url()

# Crear engine con opciones SSL para PostgreSQL
if DATABASE_URL.startswith("postgresql"):
    # Detectar si es Render (usa postgres.render.com) o local
    if "render.com" in DATABASE_URL:
        # Para PostgreSQL en Render, se requiere SSL
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"sslmode": "require"}
        )
    else:
        # Para PostgreSQL local (desarrollo), SSL opcional
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"sslmode": "prefer"}
        )
else:
    # Para SQLite (desarrollo local)
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


class Taller(Base):
    """Modelo de taller mecánico en PostgreSQL."""
    __tablename__ = "talleres"
    
    id = Column(String(36), primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    direccion = Column(String(500), nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    foto = Column(String(500), nullable=True)
    lat = Column(Float, default=0.0)
    lng = Column(Float, default=0.0)
    descripcion = Column(Text, nullable=True)
    calificacion = Column(Float, default=0.0)
    total_servicios = Column(Integer, default=0)
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)


class Cliente(Base):
    """Modelo de cliente en PostgreSQL."""
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
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)


class Solicitud(Base):
    """Modelo de solicitud en PostgreSQL."""
    __tablename__ = "solicitudes"

    id = Column(String(36), primary_key=True, index=True)
    cliente_id = Column(String(36), ForeignKey("clientes.id"), nullable=False)
    taller_id = Column(String(36), ForeignKey("talleres.id"), nullable=True)

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
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    
    # Estado de pago
    estado_pago = Column(String(20), default="pendiente")  # pendiente, confirmado, completado, cancelado
    monto_pago = Column(Float, nullable=True)

    # Multimedia
    imagenes = Column(Text, default="[]")  # JSON como string
    audio = Column(String(500), nullable=True)

    # Asignación
    mecanico_asignado_id = Column(String(36), nullable=True)

    # Análisis IA
    analisis_ia = Column(Text, nullable=True)  # JSON con análisis de IA

    # Timestamps
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)

    # Relaciones
    cliente = relationship("Cliente")
    taller = relationship("Taller")


class User(Base):
    """Modelo de usuario en PostgreSQL."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    nombre = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(50), default="encargado")
    tipo_usuario = Column(String(50), default="taller")  # "taller" o "cliente"
    taller_id = Column(String(36), ForeignKey("talleres.id"), nullable=True)
    intentos_fallidos = Column(Integer, default=0, nullable=False)
    bloqueado_hasta = Column(DateTime, nullable=True)
    # Campos para recuperación de contraseña
    temp_password_hash = Column(String(255), nullable=True)
    temp_password_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)
    
    # Relación
    taller = relationship("Taller")


class Factura(Base):
    """Modelo de factura/pago en PostgreSQL."""
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
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)
    
    # Relaciones
    cliente = relationship("Cliente")
    solicitud = relationship("Solicitud")


class Personal(Base):
    """Modelo de personal del taller en PostgreSQL."""
    __tablename__ = "personal"
    
    id = Column(String(36), primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    rol = Column(String(50), nullable=False)  # mecanico, electrico, grua, administrador, encargado
    estado = Column(String(50), default="disponible")  # disponible, ocupado, en_camino, regresando
    foto = Column(String(500), nullable=True)
    telefono = Column(String(50), nullable=True)
    asistencias_dia = Column(Integer, default=0)
    asistencias_mes = Column(Integer, default=0)
    taller_id = Column(String(36), ForeignKey("talleres.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)
    
    # Relación
    taller = relationship("Taller")


class Vehiculo(Base):
    """Modelo de vehículo en PostgreSQL."""
    __tablename__ = "vehiculos"

    id = Column(String(36), primary_key=True, index=True)
    cliente_id = Column(String(36), ForeignKey("clientes.id"), nullable=False, index=True)
    marca = Column(String(100), nullable=False)
    modelo = Column(String(100), nullable=False)
    anio = Column(Integer, nullable=False)
    placa = Column(String(20), nullable=False, unique=True)
    color = Column(String(50), nullable=False)
    tipo = Column(String(50), default="Sedán")
    activo = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)

    # Relación
    cliente = relationship("Cliente")


class Repuesto(Base):
    """Modelo de repuesto en inventario."""
    __tablename__ = "repuestos"

    id = Column(String(36), primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio = Column(Float, nullable=False)
    imagen = Column(String(500), nullable=True)
    disponible = Column(Boolean, default=True)
    marca = Column(String(100), nullable=True)
    categoria = Column(String(100), nullable=True)
    vehiculos_compatibles = Column(Text, default="[]")  # JSON como string
    stock = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=5)
    taller_id = Column(String(36), ForeignKey("talleres.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=get_now)
    updated_at = Column(DateTime, default=get_now, onupdate=get_now)
    
    # Relación
    taller = relationship("Taller")


class SolicitudPersonal(Base):
    """Tabla intermedia para asignar personal a solicitudes."""
    __tablename__ = "solicitud_personal"

    id = Column(String(36), primary_key=True, index=True)
    solicitud_id = Column(String(36), ForeignKey("solicitudes.id"), nullable=False)
    personal_id = Column(String(36), ForeignKey("personal.id"), nullable=False)
    rol_asignado = Column(String(50), nullable=False)
    fecha_asignacion = Column(DateTime, default=get_now)
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


def migrate_taller_columns():
    """Migrar columnas taller_id si no existen."""
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # Crear tabla talleres si no existe
        inspector = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'talleres'
            );
        """)
        result = db.execute(inspector).scalar()
        
        if not result:
            print("📋 Creando tabla talleres...")
            db.execute(text("""
                CREATE TABLE talleres (
                    id VARCHAR(36) PRIMARY KEY,
                    nombre VARCHAR(255) NOT NULL,
                    direccion VARCHAR(500),
                    telefono VARCHAR(50),
                    email VARCHAR(255),
                    lat FLOAT DEFAULT 0.0,
                    lng FLOAT DEFAULT 0.0,
                    descripcion TEXT,
                    calificacion FLOAT DEFAULT 0.0,
                    total_servicios INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            db.commit()
            print("✅ Tabla talleres creada")
        
        # Agregar columnas taller_id si no existen
        tables_to_migrate = [
            ('users', 'taller_id', 'VARCHAR(36)'),
            ('solicitudes', 'taller_id', 'VARCHAR(36)'),
            ('personal', 'taller_id', 'VARCHAR(36)'),
            ('repuestos', 'taller_id', 'VARCHAR(36)'),
        ]
        
        for table_name, column_name, column_type in tables_to_migrate:
            check_column = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = '{table_name}' AND column_name = '{column_name}'
                );
            """)
            column_exists = db.execute(check_column).scalar()
            
            if not column_exists:
                print(f"📋 Agregando columna {column_name} a tabla {table_name}...")
                db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                db.commit()
                print(f"✅ Columna {column_name} agregada a {table_name}")
                
        # Columnas de bloqueo de usuario
        auth_columns = [
            ('users', 'intentos_fallidos', 'INTEGER DEFAULT 0 NOT NULL'),
            ('users', 'bloqueado_hasta', 'TIMESTAMP NULL'),
        ]
        for table_name, column_name, column_type in auth_columns:
            check_col = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = '{table_name}' AND column_name = '{column_name}'
                );
            """)
            if not db.execute(check_col).scalar():
                print(f"📋 Agregando columna {column_name} a tabla {table_name}...")
                db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                db.commit()
                print(f"✅ Columna {column_name} agregada a {table_name}")
        
        # Agregar columna tipo_usuario si no existe
        check_tipo_usuario = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'tipo_usuario'
            );
        """)
        tipo_usuario_exists = db.execute(check_tipo_usuario).scalar()
        
        if not tipo_usuario_exists:
            print("📋 Agregando columna tipo_usuario a tabla users...")
            db.execute(text("ALTER TABLE users ADD COLUMN tipo_usuario VARCHAR(50) DEFAULT 'taller'"))
            db.commit()
            print("✅ Columna tipo_usuario agregada")
            
            # Asignar tipo_usuario a usuarios existentes según taller_id
            print("📋 Asignando tipo_usuario a usuarios existentes...")
            db.execute(text("""
                UPDATE users 
                SET tipo_usuario = CASE 
                    WHEN taller_id IS NOT NULL THEN 'taller'
                    ELSE 'cliente'
                END
                WHERE tipo_usuario IS NULL
            """))
            db.commit()
            print("✅ tipo_usuario asignado a usuarios existentes")
        
        # Agregar columna foto a talleres si no existe
        check_foto = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'talleres' AND column_name = 'foto'
            );
        """)
        foto_exists = db.execute(check_foto).scalar()
        
        if not foto_exists:
            print("📋 Agregando columna foto a tabla talleres...")
            db.execute(text("ALTER TABLE talleres ADD COLUMN foto VARCHAR(500)"))
            db.commit()
            print("✅ Columna foto agregada a talleres")
        
        # Crear taller por defecto si no existe - DESHABILITADO
        # Se permite que los usuarios creen sus propios talleres manualmente
        # check_taller = text("SELECT COUNT(*) FROM talleres WHERE id = 'taller-default-001'")
        # taller_count = db.execute(check_taller).scalar()
        #
        # if taller_count == 0:
        #     print("📋 Creando taller por defecto...")
        #     db.execute(text("""
        #         INSERT INTO talleres (id, nombre, email, created_at, updated_at)
        #         VALUES ('taller-default-001', 'Taller Principal', 'taller@asistego.com', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        #     """))
        #     db.commit()
        #     print("✅ Taller por defecto creado")
        #
        # # Asignar datos existentes al taller por defecto
        # for table_name in ['users', 'solicitudes', 'personal', 'repuestos']:
        #     update_query = text(f"""
        #         UPDATE {table_name}
        #         SET taller_id = 'taller-default-001'
        #         WHERE taller_id IS NULL
        #     """)
        #     db.execute(update_query)
        #     db.commit()
        #     print(f"✅ Datos de {table_name} asignados al taller por defecto")
            
        print("✅ Migración completada")
        
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_analisis_ia_column():
    """Migrar columna analisis_ia si no existe en la tabla solicitudes."""
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # Verificar si la columna analisis_ia existe
        check_column = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'solicitudes' AND column_name = 'analisis_ia'
            );
        """)
        
        if not db.execute(check_column).scalar():
            print("📋 Agregando columna analisis_ia a tabla solicitudes...")
            db.execute(text("ALTER TABLE solicitudes ADD COLUMN analisis_ia TEXT"))
            db.commit()
            print("✅ Columna analisis_ia agregada a solicitudes")
        else:
            print("✅ Columna analisis_ia ya existe en solicitudes")
        
    except Exception as e:
        print(f"❌ Error migrando columna analisis_ia: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_lat_lng_columns():
    """Migrar columnas lat y lng si no existen en tabla solicitudes."""
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # Columnas lat/lng para solicitudes
        lat_lng_columns = [
            ('solicitudes', 'lat', 'FLOAT NULL'),
            ('solicitudes', 'lng', 'FLOAT NULL'),
        ]

        for table_name, column_name, column_type in lat_lng_columns:
            check_column = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = '{table_name}' AND column_name = '{column_name}'
                );
            """)
            column_exists = db.execute(check_column).scalar()

            if not column_exists:
                print(f"📋 Agregando columna {column_name} a tabla {table_name}...")
                db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                db.commit()
                print(f"✅ Columna {column_name} agregada a {table_name}")
            else:
                print(f"✅ Columna {column_name} ya existe en {table_name}")

    except Exception as e:
        print(f"❌ Error migrando columnas lat/lng: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_temp_password_columns():
    """Migrar columnas para recuperación de contraseña si no existen."""
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # Columnas para recuperación de contraseña
        temp_password_columns = [
            ('users', 'temp_password_hash', 'VARCHAR(255) NULL'),
            ('users', 'temp_password_expires_at', 'TIMESTAMP NULL'),
        ]

        for table_name, column_name, column_type in temp_password_columns:
            check_column = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = '{table_name}' AND column_name = '{column_name}'
                );
            """)
            column_exists = db.execute(check_column).scalar()

            if not column_exists:
                print(f"📋 Agregando columna {column_name} a tabla {table_name}...")
                db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                db.commit()
                print(f"✅ Columna {column_name} agregada a {table_name}")
            else:
                print(f"✅ Columna {column_name} ya existe en {table_name}")

    except Exception as e:
        print(f"❌ Error migrando columnas de recuperación de contraseña: {e}")
        db.rollback()
    finally:
        db.close()


def create_tables():
    """Crear todas las tablas y migrar columnas."""
    try:
        Base.metadata.create_all(bind=engine)
        migrate_taller_columns()
        migrate_analisis_ia_column()
        migrate_temp_password_columns()
        migrate_lat_lng_columns()
    except Exception as e:
        print(f"[DATABASE] Error durante la creación/migración de tablas: {str(e)}")
        raise


def init_mock_data():
    """Inicializar datos de prueba en PostgreSQL."""
    db = SessionLocal()
    try:
        # Crear usuario administrador si no existe
        from utils.security import hash_password
        admin_user = db.query(User).filter(User.email == "admin@gmail.com").first()
        if not admin_user:
            admin_user = User(
                email="admin@gmail.com",
                nombre="Administrador",
                password_hash=hash_password("admin123"),
                rol="administrador",
                tipo_usuario="administrador",
                taller_id=None
            )
            db.add(admin_user)
            db.commit()
            print("✅ Usuario admin creado: admin@gmail.com / admin123")
        else:
            print("ℹ️ Usuario admin ya existe")

        # No crear datos de prueba (clientes, personal, vehículos)
        # para mostrar solo datos reales en el dashboard
        print("ℹ️ Datos de prueba deshabilitados - usando solo datos reales")
    except Exception as e:
        print(f"⚠️ Error creando datos de prueba: {e}")
        db.rollback()
    finally:
        db.close()
