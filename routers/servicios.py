from fastapi import APIRouter, HTTPException
from typing import List
from models import Servicio, ServicioCreate, ServicioUpdate, StatsResponse
from database import db

router = APIRouter()


@router.get("/", response_model=List[Servicio])
def listar_servicios():
    """Listar todos los servicios completados."""
    return db.get_all("servicios")


@router.get("/{servicio_id}", response_model=Servicio)
def obtener_servicio(servicio_id: str):
    """Obtener servicio por ID."""
    servicio = db.get_by_id("servicios", servicio_id)
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    return servicio


@router.post("/", response_model=Servicio)
def crear_servicio(servicio: ServicioCreate):
    """Registrar servicio completado."""
    # Validar cliente existe
    cliente = db.get_by_id("clientes", servicio.cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    data = servicio.model_dump()
    data["cliente"] = cliente
    return db.create("servicios", data)


@router.put("/{servicio_id}", response_model=Servicio)
def actualizar_servicio(servicio_id: str, servicio: ServicioUpdate):
    """Actualizar servicio."""
    existing = db.get_by_id("servicios", servicio_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    updated = db.update("servicios", servicio_id, servicio.model_dump(exclude_unset=True))
    return updated


@router.get("/stats/resumen")
def estadisticas_servicios():
    """Obtener estadísticas de servicios."""
    servicios = db.get_all("servicios")
    
    total = len(servicios)
    ingresos = sum(s.get("monto", 0) for s in servicios)
    
    return {
        "total_servicios": total,
        "ingresos_totales": ingresos,
        "promedio_monto": ingresos / total if total > 0 else 0
    }
