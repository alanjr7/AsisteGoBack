from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Cargar variables de entorno desde .env al inicio (solo para desarrollo local)
from dotenv import load_dotenv
load_dotenv(override=False)  # No sobreescribir variables de entorno existentes (como en Render)
print("[MAIN] Variables de entorno cargadas")

# Importar routers
from routers import auth, clientes, solicitudes, repuestos, solicitudes_repuesto
from routers import servicios, notificaciones, personal, facturas, taller, chat, talleres
from routers import upload, grua, evidencias, comprobantes, websocket, pagos, vehiculos, reportes, evaluaciones
from routers import admin

# Importar configuración de base de datos
from database_sql import create_tables, get_db, User, init_mock_data
from sqlalchemy.orm import Session
from fastapi import Depends

# Rate limiting
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from utils.rate_limiter import limiter
except ImportError as e:
    print(f"⚠️ Error importando rate limiting: {str(e)}")
    limiter = None

app = FastAPI(
    title="Asistego API",
    description="API para el sistema de asistencia mecánica AsisteGO",
    version="1.0.0"
)

# Configurar rate limiting
if limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    print("⚠️ Rate limiting deshabilitado debido a error de importación")

# Configurar directorio de uploads
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "audio"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "comprobantes"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "perfiles"), exist_ok=True)

# Servir archivos estáticos (imágenes, audios, comprobantes)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

#sql Configurar CORS para producción (dominios específicos)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://asistego-front.netlify.app",  # Frontend actual en Netlify
        "https://comforting-taiyaki-e1534c.netlify.app",  # Frontend anterior
        "http://181.115.129.246",  # Dispositivo móvil IP
        "https://189.28.71.142",
        "http://181.115.129.246:8080",  # Dispositivo móvil IP con puerto
        "http://localhost:4200",  # Desarrollo local Angular
        "http://localhost:8080",  # Flutter web default
        "http://localhost:5000",  # Flutter web alternativo
        "http://localhost:3000",  # React/Vue dev server
    ],
    allow_credentials=True,  # Permitir cookies/tokens de autenticación
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
app.include_router(clientes.router, prefix="/clientes", tags=["Clientes"])
app.include_router(solicitudes.router, prefix="/solicitudes", tags=["Solicitudes"])
app.include_router(repuestos.router, prefix="/repuestos", tags=["Repuestos"])
app.include_router(solicitudes_repuesto.router, prefix="/solicitudes-repuesto", tags=["Solicitudes de Repuesto"])
app.include_router(servicios.router, prefix="/servicios", tags=["Servicios"])
app.include_router(notificaciones.router, prefix="/notificaciones", tags=["Notificaciones"])
app.include_router(personal.router, prefix="/personal", tags=["Personal"])
app.include_router(facturas.router, prefix="/facturas", tags=["Facturas"])
app.include_router(taller.router, prefix="/taller", tags=["Taller"])
app.include_router(talleres.router, tags=["Talleres"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(upload.router, prefix="/upload", tags=["Upload"])
app.include_router(grua.router, prefix="/grua", tags=["Grúa"])
app.include_router(evidencias.router, prefix="/evidencias", tags=["Evidencias"])
app.include_router(comprobantes.router, prefix="/comprobantes", tags=["Comprobantes"])
app.include_router(pagos.router, prefix="/pagos", tags=["Pagos"])
app.include_router(vehiculos.router, prefix="/vehiculos", tags=["Vehículos"])
app.include_router(reportes.router, prefix="/reportes", tags=["Reportes"])
app.include_router(evaluaciones.router, prefix="/evaluaciones", tags=["Evaluaciones"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
app.include_router(admin.router, tags=["Administración"])


@app.get("/")
def read_root():
    return {
        "message": "Bienvenido a Asistego API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/db-check")
def check_database(db: Session = Depends(get_db)):
    """Verificar conexión a la base de datos y listar usuarios."""
    try:
        users = db.query(User).all()
        return {
            "status": "connected",
            "database": "PostgreSQL",
            "users_count": len(users),
            "users": [{"id": u.id, "email": u.email, "nombre": u.nombre, "rol": u.rol} for u in users]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.on_event("startup")
def startup_event():
    """Crear tablas de base de datos al iniciar."""
    print("🚀 Iniciando Asistego API...")
    try:
        create_tables()
        print("✅ Tablas de base de datos verificadas/creadas")
    except Exception as e:
        print(f"⚠️ Error al crear tablas de base de datos: {str(e)}")
        print("⚠️ La API continuará iniciando, pero algunas funciones pueden no estar disponibles")
    # init_mock_data()  # Commented out to use only real data
