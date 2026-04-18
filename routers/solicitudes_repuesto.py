from fastapi import APIRouter, HTTPException
from typing import List, Optional
from models import SolicitudRepuesto, SolicitudRepuestoCreate, SolicitudRepuestoUpdate, EstadoSolicitudRepuesto
from database import db

router = APIRouter()


@router.get("/", response_model=List[SolicitudRepuesto])
def listar_solicitudes_repuesto(estado: Optional[EstadoSolicitudRepuesto] = None):
    """Listar solicitudes de repuesto."""
    solicitudes = db.get_all("solicitudes_repuesto")
    
    if estado:
        solicitudes = [s for s in solicitudes if s.get("estado") == estado]
    
    # Enriquecer con datos de repuesto y cliente
    for s in solicitudes:
        s["repuesto"] = db.get_by_id("repuestos", s.get("repuesto_id"))
        s["cliente"] = db.get_by_id("clientes", s.get("cliente_id"))
    
    return solicitudes


@router.get("/{solicitud_id}", response_model=SolicitudRepuesto)
def obtener_solicitud_repuesto(solicitud_id: str):
    """Obtener solicitud de repuesto por ID."""
    solicitud = db.get_by_id("solicitudes_repuesto", solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    solicitud["repuesto"] = db.get_by_id("repuestos", solicitud.get("repuesto_id"))
    solicitud["cliente"] = db.get_by_id("clientes", solicitud.get("cliente_id"))
    return solicitud


@router.post("/", response_model=SolicitudRepuesto)
def crear_solicitud_repuesto(solicitud: SolicitudRepuestoCreate):
    """Crear nueva solicitud de repuesto."""
    # Validar repuesto y cliente existen
    repuesto = db.get_by_id("repuestos", solicitud.repuesto_id)
    if not repuesto:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    
    cliente = db.get_by_id("clientes", solicitud.cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    data = solicitud.model_dump()
    data["repuesto"] = repuesto
    data["cliente"] = cliente
    return db.create("solicitudes_repuesto", data)


@router.put("/{solicitud_id}/estado")
def cambiar_estado_solicitud_repuesto(solicitud_id: str, estado: EstadoSolicitudRepuesto):
    """Cambiar estado de la solicitud de repuesto."""
    existing = db.get_by_id("solicitudes_repuesto", solicitud_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    updated = db.update("solicitudes_repuesto", solicitud_id, {"estado": estado})
    return updated


@router.delete("/{solicitud_id}")
def cancelar_solicitud_repuesto(solicitud_id: str):
    """Cancelar solicitud de repuesto."""
    existing = db.get_by_id("solicitudes_repuesto", solicitud_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    db.delete("solicitudes_repuesto", solicitud_id)
    return {"success": True, "message": "Solicitud de repuesto cancelada"}
