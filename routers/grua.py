"""
Router para gestión de grúa con geolocalización en tiempo real.
Incluye: actualización de ubicación, listado de gruistas disponibles,
asignación automática por proximidad.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
from datetime import datetime
import math
from database import db
from models import (
    UbicacionGrua, UbicacionGruaUpdate, AsignacionGruaRequest, AsignacionGruaResponse,
    Personal, EstadoPersonal, Solicitud, EstadoSolicitud
)

router = APIRouter()


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calcula la distancia entre dos puntos geográficos usando la fórmula de Haversine.
    Retorna la distancia en kilómetros.
    """
    R = 6371  # Radio de la Tierra en kilómetros
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def calcular_tiempo_estimado(distancia_km: float, velocidad_promedio_kmh: float = 30) -> int:
    """
    Calcula el tiempo estimado de llegada en minutos.
    Velocidad promedio por defecto: 30 km/h (tráfico urbano).
    """
    tiempo_horas = distancia_km / velocidad_promedio_kmh
    return max(1, int(tiempo_horas * 60))  # Mínimo 1 minuto


@router.post("/ubicacion")
def actualizar_ubicacion(
    data: UbicacionGruaUpdate,
    gruista_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Actualizar la ubicación GPS de un gruista.
    Se llama desde la app móvil del gruista cada 5-10 segundos.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Verificar que el gruista existe y tiene rol de grúa
    gruista = db.get_by_id("personal", gruista_id)
    if not gruista:
        raise HTTPException(status_code=404, detail="Gruista no encontrado")
    
    if gruista.get("rol") != "grua":
        raise HTTPException(status_code=403, detail="El usuario no tiene rol de grúa")
    
    # Crear o actualizar registro de ubicación
    ubicacion_data = {
        "gruista_id": gruista_id,
        "lat": data.lat,
        "lng": data.lng,
        "timestamp": datetime.now(),
    }
    
    # Si se proporcionan campos opcionales, agregarlos
    if data.disponible is not None:
        ubicacion_data["disponible"] = data.disponible
    if data.en_servicio is not None:
        ubicacion_data["en_servicio"] = data.en_servicio
    if data.solicitud_id is not None:
        ubicacion_data["solicitud_id"] = data.solicitud_id
    
    # Buscar si ya existe una ubicación para este gruista
    ubicaciones = db.get_all("ubicaciones_grua")
    ubicacion_existente = None
    for u in ubicaciones:
        if u.get("gruista_id") == gruista_id:
            ubicacion_existente = u
            break
    
    if ubicacion_existente:
        # Actualizar
        ubicacion = db.update("ubicaciones_grua", ubicacion_existente["id"], ubicacion_data)
    else:
        # Crear nueva
        ubicacion = db.create("ubicaciones_grua", ubicacion_data)
    
    return ubicacion


@router.get("/disponibles")
def listar_gruistas_disponibles(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    authorization: Optional[str] = Header(None)
):
    """
    Listar todos los gruistas disponibles.
    Si se proporciona lat/lng, incluye la distancia calculada.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    ubicaciones = db.get_all("ubicaciones_grua")
    gruistas_disponibles = []
    
    for u in ubicaciones:
        # Solo gruistas disponibles y no en servicio
        if u.get("disponible") and not u.get("en_servicio"):
            gruista = db.get_by_id("personal", u.get("gruista_id"))
            if gruista:
                item = {
                    "gruista_id": u.get("gruista_id"),
                    "nombre": gruista.get("nombre"),
                    "foto": gruista.get("foto"),
                    "telefono": gruista.get("telefono"),
                    "lat": u.get("lat"),
                    "lng": u.get("lng"),
                    "timestamp": u.get("timestamp"),
                }
                
                # Calcular distancia si se proporcionó lat/lng del cliente
                if lat is not None and lng is not None:
                    distancia = haversine_distance(
                        lat, lng,
                        u.get("lat", 0), u.get("lng", 0)
                    )
                    item["distancia_km"] = round(distancia, 2)
                    item["tiempo_estimado_min"] = calcular_tiempo_estimado(distancia)
                
                gruistas_disponibles.append(item)
    
    # Ordenar por distancia si se proporcionó lat/lng
    if lat is not None and lng is not None:
        gruistas_disponibles.sort(key=lambda x: x.get("distancia_km", float('inf')))
    
    return gruistas_disponibles


@router.get("/{gruista_id}/ubicacion")
def obtener_ubicacion_gruista(
    gruista_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Obtener la ubicación actual de un gruista específico.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    ubicaciones = db.get_all("ubicaciones_grua")
    ubicacion = None
    
    for u in ubicaciones:
        if u.get("gruista_id") == gruista_id:
            ubicacion = u
            break
    
    if not ubicacion:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    
    gruista = db.get_by_id("personal", gruista_id)
    
    return {
        "gruista_id": gruista_id,
        "nombre": gruista.get("nombre") if gruista else None,
        "lat": ubicacion.get("lat"),
        "lng": ubicacion.get("lng"),
        "disponible": ubicacion.get("disponible"),
        "en_servicio": ubicacion.get("en_servicio"),
        "solicitud_id": ubicacion.get("solicitud_id"),
        "timestamp": ubicacion.get("timestamp"),
    }


@router.post("/asignar", response_model=AsignacionGruaResponse)
def asignar_grua_automatica(
    request: AsignacionGruaRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Asignar automáticamente la grúa más cercana a una solicitud.
    Algoritmo:
    1. Buscar todos los gruistas disponibles
    2. Calcular distancia a la ubicación del cliente
    3. Seleccionar el más cercano
    4. Marcar gruista como 'en_servicio'
    5. Actualizar solicitud con el gruista asignado
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Verificar que la solicitud existe
    solicitud = db.get_by_id("solicitudes", request.solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Verificar que la solicitud es de tipo grúa o requiere grúa
    # (asumimos que todas las solicitudes pueden requerir grúa si el cliente lo indica)
    
    # Buscar gruistas disponibles
    ubicaciones = db.get_all("ubicaciones_grua")
    gruistas_cercanos = []
    
    for u in ubicaciones:
        if u.get("disponible") and not u.get("en_servicio"):
            distancia = haversine_distance(
                request.lat_cliente, request.lng_cliente,
                u.get("lat", 0), u.get("lng", 0)
            )
            gruistas_cercanos.append({
                "gruista_id": u.get("gruista_id"),
                "ubicacion_id": u.get("id"),
                "distancia_km": distancia,
                "lat": u.get("lat"),
                "lng": u.get("lng"),
            })
    
    if not gruistas_cercanos:
        return AsignacionGruaResponse(
            success=False,
            message="No hay gruistas disponibles en este momento"
        )
    
    # Ordenar por distancia y seleccionar el más cercano
    gruistas_cercanos.sort(key=lambda x: x["distancia_km"])
    seleccionado = gruistas_cercanos[0]
    
    # Obtener información del gruista
    gruista = db.get_by_id("personal", seleccionado["gruista_id"])
    
    # Marcar gruista como 'en_servicio' y asignar a la solicitud
    db.update("ubicaciones_grua", seleccionado["ubicacion_id"], {
        "en_servicio": True,
        "solicitud_id": request.solicitud_id,
        "disponible": False
    })
    
    # Actualizar la solicitud con el gruista asignado
    db.update("solicitudes", request.solicitud_id, {
        "gruista_asignado": gruista,
        "gruista_id": seleccionado["gruista_id"],
        "estado": "en_camino",
        "distancia_gruista_km": round(seleccionado["distancia_km"], 2),
        "tiempo_estimado_llegada_min": calcular_tiempo_estimado(seleccionado["distancia_km"])
    })
    
    return AsignacionGruaResponse(
        success=True,
        message=f"Gruista {gruista.get('nombre')} asignado exitosamente",
        gruista_id=seleccionado["gruista_id"],
        gruista_nombre=gruista.get("nombre"),
        distancia_km=round(seleccionado["distancia_km"], 2),
        tiempo_estimado_min=calcular_tiempo_estimado(seleccionado["distancia_km"])
    )


@router.post("/liberar/{gruista_id}")
def liberar_grua(
    gruista_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Liberar a un gruista después de completar un servicio.
    Marca al gruista como disponible nuevamente.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    ubicaciones = db.get_all("ubicaciones_grua")
    ubicacion = None
    
    for u in ubicaciones:
        if u.get("gruista_id") == gruista_id:
            ubicacion = u
            break
    
    if not ubicacion:
        raise HTTPException(status_code=404, detail="Gruista no encontrado")
    
    # Liberar gruista
    db.update("ubicaciones_grua", ubicacion["id"], {
        "en_servicio": False,
        "solicitud_id": None,
        "disponible": True
    })
    
    # Si había una solicitud asignada, marcarla como finalizada
    solicitud_id = ubicacion.get("solicitud_id")
    if solicitud_id:
        solicitud = db.get_by_id("solicitudes", solicitud_id)
        if solicitud and solicitud.get("estado") == "en_camino":
            db.update("solicitudes", solicitud_id, {
                "estado": "finalizada",
                "fecha_finalizacion": datetime.now()
            })
    
    return {
        "success": True,
        "message": "Gruista liberado exitosamente"
    }


@router.get("/solicitud/{solicitud_id}/tracking")
def tracking_solicitud_grua(
    solicitud_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Obtener información de tracking en tiempo real para una solicitud de grúa.
    Retorna la ubicación actual del gruista asignado y la distancia al cliente.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Obtener la solicitud
    solicitud = db.get_by_id("solicitudes", solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    gruista_id = solicitud.get("gruista_id")
    if not gruista_id:
        raise HTTPException(status_code=400, detail="No hay gruista asignado a esta solicitud")
    
    # Obtener ubicación actual del gruista
    ubicaciones = db.get_all("ubicaciones_grua")
    ubicacion_gruista = None
    
    for u in ubicaciones:
        if u.get("gruista_id") == gruista_id:
            ubicacion_gruista = u
            break
    
    if not ubicacion_gruista:
        raise HTTPException(status_code=404, detail="Ubicación del gruista no encontrada")
    
    # Obtener ubicación del cliente de la solicitud
    cliente = solicitud.get("cliente", {})
    lat_cliente = cliente.get("lat", 0)
    lng_cliente = cliente.get("lng", 0)
    
    # Calcular distancia actual
    distancia_km = haversine_distance(
        lat_cliente, lng_cliente,
        ubicacion_gruista.get("lat", 0),
        ubicacion_gruista.get("lng", 0)
    )
    
    gruista = db.get_by_id("personal", gruista_id)
    
    return {
        "solicitud_id": solicitud_id,
        "estado": solicitud.get("estado"),
        "gruista": {
            "id": gruista_id,
            "nombre": gruista.get("nombre") if gruista else None,
            "foto": gruista.get("foto") if gruista else None,
            "telefono": gruista.get("telefono") if gruista else None,
            "lat": ubicacion_gruista.get("lat"),
            "lng": ubicacion_gruista.get("lng"),
            "timestamp": ubicacion_gruista.get("timestamp"),
        },
        "cliente": {
            "lat": lat_cliente,
            "lng": lng_cliente,
        },
        "distancia_actual_km": round(distancia_km, 2),
        "tiempo_estimado_min": calcular_tiempo_estimado(distancia_km)
    }
