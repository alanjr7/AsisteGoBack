from fastapi import APIRouter, HTTPException, Header, Query, Depends
from typing import Optional
from models import Taller, TallerCreate, TallerUpdate, StatsResponse
from database_sql import get_db, Taller as TallerDB, User, Solicitud, Personal, Factura
from database import db as memory_db
from sqlalchemy.orm import Session
from utils.security import decode_access_token
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


def get_current_user_from_token(authorization: str | None, db: Session):
    """Extraer el usuario actual del token JWT desde PostgreSQL."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload:
        return None
    email = payload.get("sub")
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


@router.get("/", response_model=Taller)
def obtener_taller(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Obtener información del taller del usuario autenticado."""
    # Obtener usuario autenticado desde PostgreSQL
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    # Obtener taller desde PostgreSQL
    taller = db.query(TallerDB).filter(TallerDB.id == user.taller_id).first()
    if not taller:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    
    return Taller(
        id=taller.id,
        nombre=taller.nombre,
        direccion=taller.direccion,
        telefono=taller.telefono,
        email=taller.email,
        foto=taller.foto,
        lat=taller.lat or 0.0,
        lng=taller.lng or 0.0,
        descripcion=taller.descripcion,
        calificacion=taller.calificacion or 0.0,
        total_servicios=taller.total_servicios or 0
    )


@router.put("/", response_model=Taller)
def actualizar_taller(
    taller: TallerUpdate,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Actualizar información del taller del usuario autenticado."""
    # Obtener usuario autenticado
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    # Obtener taller desde PostgreSQL
    taller_db = db.query(TallerDB).filter(TallerDB.id == user.taller_id).first()
    if not taller_db:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    
    # Actualizar campos
    data = taller.model_dump(exclude_unset=True)
    for field, value in data.items():
        if hasattr(taller_db, field):
            setattr(taller_db, field, value)
    
    db.commit()
    db.refresh(taller_db)

    return Taller(
        id=taller_db.id,
        nombre=taller_db.nombre,
        direccion=taller_db.direccion,
        telefono=taller_db.telefono,
        email=taller_db.email,
        foto=taller_db.foto,
        lat=taller_db.lat or 0.0,
        lng=taller_db.lng or 0.0,
        descripcion=taller_db.descripcion,
        calificacion=taller_db.calificacion or 0.0,
        total_servicios=taller_db.total_servicios or 0
    )


@router.get("/stats", response_model=StatsResponse)
def estadisticas_taller(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Obtener estadísticas generales del taller del usuario autenticado."""
    # Obtener usuario autenticado
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    # Obtener estadísticas desde PostgreSQL
    total_solicitudes = db.query(Solicitud).filter(Solicitud.taller_id == user.taller_id).count()
    
    # Calcular ingresos desde facturas (join con solicitudes)
    facturas = db.query(Factura).join(Solicitud, Factura.solicitud_id == Solicitud.id).filter(
        Solicitud.taller_id == user.taller_id,
        Factura.enviada == True
    ).all()
    ingresos = sum(f.total for f in facturas)
    
    # Obtener taller para calificación
    taller = db.query(TallerDB).filter(TallerDB.id == user.taller_id).first()
    calificacion = (taller.calificacion if taller else 0.0) or 0.0
    
    return StatsResponse(
        total_servicios=total_solicitudes or 0,
        servicios_hoy=0,
        servicios_mes=0,
        ingresos_totales=ingresos or 0.0,
        calificacion_promedio=calificacion
    )


@router.get("/cercanos")
def obtener_talleres_cercanos(
    lat: float = Query(..., description="Latitud de la ubicación del usuario"),
    lng: float = Query(..., description="Longitud de la ubicación del usuario"),
    radio_km: float = Query(10.0, description="Radio de búsqueda en kilómetros"),
    db: Session = Depends(get_db)
):
    """Obtener talleres cercanos a una ubicación dentro de un radio específico."""
    # Obtener todos los talleres de PostgreSQL
    talleres = db.query(TallerDB).all()
    
    if not talleres:
        raise HTTPException(status_code=404, detail="No hay talleres registrados")
    
    resultados = []
    for taller in talleres:
        taller_lat = taller.lat or -17.7833
        taller_lng = taller.lng or -63.1821
        
        # Calcular distancia
        distancia = calcular_distancia(lat, lng, taller_lat, taller_lng)
        
        if distancia <= radio_km:
            resultados.append({
                "id": taller.id,
                "nombre": taller.nombre,
                "direccion": taller.direccion or "Santa Cruz, Bolivia",
                "calificacion": taller.calificacion or 4.5,
                "distancia": round(distancia, 1),
                "disponible": True,
                "telefono": taller.telefono or "00000000",
                "lat": taller_lat,
                "lng": taller_lng,
            })
    
    # Si no hay talleres en el radio, devolver el más cercano
    if not resultados and talleres:
        taller = talleres[0]
        taller_lat = taller.lat or -17.7833
        taller_lng = taller.lng or -63.1821
        distancia = calcular_distancia(lat, lng, taller_lat, taller_lng)
        
        return [
            {
                "id": taller.id,
                "nombre": taller.nombre,
                "direccion": taller.direccion or "Santa Cruz, Bolivia",
                "calificacion": taller.calificacion or 4.5,
                "distancia": round(distancia, 1),
                "disponible": True,
                "telefono": taller.telefono or "00000000",
                "lat": taller_lat,
                "lng": taller_lng,
            }
        ]
    
    return resultados
