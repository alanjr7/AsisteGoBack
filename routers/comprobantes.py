"""
Router para gestión de comprobantes de pago.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
from datetime import datetime
from database import db
from models import ComprobantePago, ComprobantePagoCreate, MetodoPago

router = APIRouter()


@router.get("/solicitud/{solicitud_id}", response_model=List[ComprobantePago])
def listar_comprobantes_solicitud(
    solicitud_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Listar todos los comprobantes de pago de una solicitud.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Verificar que la solicitud existe
    solicitud = db.get_by_id("solicitudes", solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    comprobantes = db.get_all("comprobantes_pago")
    
    # Filtrar por solicitud
    resultado = [c for c in comprobantes if c.get("solicitud_id") == solicitud_id]
    
    # Ordenar por fecha (más reciente primero)
    resultado.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
    
    return resultado


@router.post("/", response_model=ComprobantePago)
def crear_comprobante(
    data: ComprobantePagoCreate,
    authorization: Optional[str] = Header(None)
):
    """
    Registrar un nuevo comprobante de pago.
    La subida de la imagen del comprobante ya debe haberse hecho vía /upload/comprobante.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Verificar que la solicitud existe
    solicitud = db.get_by_id("solicitudes", data.solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Crear el comprobante
    comprobante_data = data.model_dump()
    comprobante_data["timestamp"] = datetime.now()
    
    comprobante = db.create("comprobantes_pago", comprobante_data)
    
    return comprobante


@router.get("/{comprobante_id}", response_model=ComprobantePago)
def obtener_comprobante(
    comprobante_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Obtener un comprobante específico por ID.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    comprobante = db.get_by_id("comprobantes_pago", comprobante_id)
    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    
    return comprobante


@router.put("/{comprobante_id}/verificar")
def verificar_comprobante(
    comprobante_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Marcar un comprobante como verificado (por el taller).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    comprobante = db.get_by_id("comprobantes_pago", comprobante_id)
    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    
    comprobante_actualizado = db.update("comprobantes_pago", comprobante_id, {
        "verificado": True
    })
    
    return comprobante_actualizado


@router.put("/{comprobante_id}/rechazar")
def rechazar_comprobante(
    comprobante_id: str,
    motivo: str,
    authorization: Optional[str] = Header(None)
):
    """
    Marcar un comprobante como rechazado (por el taller).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    comprobante = db.get_by_id("comprobantes_pago", comprobante_id)
    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    
    comprobante_actualizado = db.update("comprobantes_pago", comprobante_id, {
        "verificado": False,
        "rechazado": True,
        "motivo_rechazo": motivo
    })
    
    return comprobante_actualizado


@router.delete("/{comprobante_id}")
def eliminar_comprobante(
    comprobante_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Eliminar un comprobante de pago.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    comprobante = db.get_by_id("comprobantes_pago", comprobante_id)
    if not comprobante:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    
    # TODO: Opcionalmente eliminar el archivo físico
    
    db.delete("comprobantes_pago", comprobante_id)
    
    return {"success": True, "message": "Comprobante eliminado"}


@router.get("/stats/taller")
def estadisticas_comprobantes(
    authorization: Optional[str] = Header(None)
):
    """
    Obtener estadísticas generales de comprobantes del taller.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    comprobantes = db.get_all("comprobantes_pago")
    
    total = len(comprobantes)
    verificados = sum(1 for c in comprobantes if c.get("verificado"))
    pendientes = total - verificados
    rechazados = sum(1 for c in comprobantes if c.get("rechazado"))
    
    # Por método de pago
    por_metodo = {}
    for metodo in MetodoPago:
        por_metodo[metodo.value] = sum(
            1 for c in comprobantes 
            if c.get("metodo_pago") == metodo.value
        )
    
    return {
        "total": total,
        "verificados": verificados,
        "pendientes": pendientes,
        "rechazados": rechazados,
        "por_metodo": por_metodo
    }
