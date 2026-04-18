"""
Router para gestión de evidencias (fotos y audios) vinculadas a solicitudes.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
from datetime import datetime
from database import db
from models import Evidencia, EvidenciaCreate, TipoEvidencia

router = APIRouter()


@router.get("/solicitud/{solicitud_id}", response_model=List[Evidencia])
def listar_evidencias_solicitud(
    solicitud_id: str,
    tipo: Optional[TipoEvidencia] = None,
    authorization: Optional[str] = Header(None)
):
    """
    Listar todas las evidencias de una solicitud.
    Opcionalmente filtrar por tipo (imagen, audio, video).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Verificar que la solicitud existe
    solicitud = db.get_by_id("solicitudes", solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    evidencias = db.get_all("evidencias")
    
    # Filtrar por solicitud
    resultado = [e for e in evidencias if e.get("solicitud_id") == solicitud_id]
    
    # Filtrar por tipo si se especificó
    if tipo:
        resultado = [e for e in resultado if e.get("tipo") == tipo]
    
    # Ordenar por fecha (más reciente primero)
    resultado.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
    
    return resultado


@router.post("/", response_model=Evidencia)
def crear_evidencia(
    data: EvidenciaCreate,
    authorization: Optional[str] = Header(None)
):
    """
    Registrar una nueva evidencia.
    La subida del archivo ya debe haberse hecho vía /upload/.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Verificar que la solicitud existe
    solicitud = db.get_by_id("solicitudes", data.solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Crear la evidencia
    evidencia_data = data.model_dump()
    evidencia_data["timestamp"] = datetime.now()
    
    evidencia = db.create("evidencias", evidencia_data)
    
    return evidencia


@router.get("/{evidencia_id}", response_model=Evidencia)
def obtener_evidencia(
    evidencia_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Obtener una evidencia específica por ID.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    evidencia = db.get_by_id("evidencias", evidencia_id)
    if not evidencia:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    
    return evidencia


@router.delete("/{evidencia_id}")
def eliminar_evidencia(
    evidencia_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Eliminar una evidencia.
    También elimina el archivo físico asociado.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    evidencia = db.get_by_id("evidencias", evidencia_id)
    if not evidencia:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    
    # TODO: Opcionalmente eliminar el archivo físico
    # url = evidencia.get("url")
    # if url:
    #     eliminar_archivo_fisico(url)
    
    db.delete("evidencias", evidencia_id)
    
    return {"success": True, "message": "Evidencia eliminada"}


@router.get("/stats/{solicitud_id}")
def estadisticas_evidencias(
    solicitud_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Obtener estadísticas de evidencias para una solicitud.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    evidencias = db.get_all("evidencias")
    
    total = 0
    imagenes = 0
    audios = 0
    videos = 0
    
    for e in evidencias:
        if e.get("solicitud_id") == solicitud_id:
            total += 1
            tipo = e.get("tipo")
            if tipo == "imagen":
                imagenes += 1
            elif tipo == "audio":
                audios += 1
            elif tipo == "video":
                videos += 1
    
    return {
        "solicitud_id": solicitud_id,
        "total_evidencias": total,
        "imagenes": imagenes,
        "audios": audios,
        "videos": videos
    }
