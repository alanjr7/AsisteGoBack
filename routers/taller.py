from fastapi import APIRouter, HTTPException, Header, Query
from models import Taller, TallerCreate, TallerUpdate, StatsResponse
from database import db
import math

router = APIRouter()


def calcular_distancia(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calcular distancia entre dos puntos usando la fórmula de Haversine."""
    R = 6371  # Radio de la Tierra en km
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def get_current_user_from_token(authorization: str | None):
    """Extraer el usuario actual del token JWT."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    if not token.startswith("fake-jwt-token-"):
        return None
    email = token.replace("fake-jwt-token-", "")
    return db.users.get(email)


@router.get("/", response_model=Taller)
def obtener_taller(authorization: str = Header(None)):
    """Obtener información del taller."""
    if not db.taller:
        raise HTTPException(status_code=404, detail="Información del taller no encontrada")

    # Obtener usuario autenticado y usar su nombre si está disponible
    user = get_current_user_from_token(authorization)
    if user:
        db.taller["nombre"] = user.get("nombre", db.taller.get("nombre"))
        db.taller["email"] = user.get("email", db.taller.get("email"))

    return db.taller


@router.put("/", response_model=Taller)
def actualizar_taller(taller: TallerUpdate):
    """Actualizar información del taller."""
    if not db.taller:
        raise HTTPException(status_code=404, detail="Información del taller no encontrada")
    
    data = taller.model_dump(exclude_unset=True)
    db.taller.update(data)
    return db.taller


@router.get("/stats", response_model=StatsResponse)
def estadisticas_taller():
    """Obtener estadísticas generales del taller."""
    servicios = db.get_all("servicios")
    facturas = db.get_all("facturas")
    
    total_servicios = len(servicios)
    ingresos = sum(f.get("total", 0) for f in facturas)
    
    return StatsResponse(
        total_servicios=total_servicios,
        servicios_hoy=0,
        servicios_mes=0,
        ingresos_totales=ingresos,
        calificacion_promedio=db.taller.get("calificacion", 0) if db.taller else 0
    )


@router.get("/cercanos")
def obtener_talleres_cercanos(
    lat: float = Query(..., description="Latitud de la ubicación del usuario"),
    lng: float = Query(..., description="Longitud de la ubicación del usuario"),
    radio_km: float = Query(10.0, description="Radio de búsqueda en kilómetros")
):
    """Obtener talleres cercanos a una ubicación dentro de un radio específico."""
    if not db.taller:
        raise HTTPException(status_code=404, detail="No hay talleres registrados")
    
    # Usar la ubicación del taller principal o ubicación mock
    taller_lat = db.taller.get("lat", -17.7833)
    taller_lng = db.taller.get("lng", -63.1821)
    
    # Calcular distancia
    distancia = calcular_distancia(lat, lng, taller_lat, taller_lng)
    
    # Si está dentro del radio, devolver el taller
    if distancia <= radio_km:
        return [
            {
                "id": db.taller.get("id", "1"),
                "nombre": db.taller.get("nombre", "Taller Principal"),
                "direccion": db.taller.get("ubicacion", "Santa Cruz, Bolivia"),
                "calificacion": db.taller.get("calificacion", 4.5),
                "distancia": round(distancia, 1),
                "disponible": True,
                "telefono": db.taller.get("telefono", "00000000"),
                "lat": taller_lat,
                "lng": taller_lng,
            }
        ]
    
    # Si no hay talleres cercanos, devolver taller principal con distancia
    return [
        {
            "id": db.taller.get("id", "1"),
            "nombre": db.taller.get("nombre", "Taller Principal"),
            "direccion": db.taller.get("ubicacion", "Santa Cruz, Bolivia"),
            "calificacion": db.taller.get("calificacion", 4.5),
            "distancia": round(distancia, 1),
            "disponible": True,
            "telefono": db.taller.get("telefono", "00000000"),
            "lat": taller_lat,
            "lng": taller_lng,
        }
    ]
