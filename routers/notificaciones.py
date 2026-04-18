from fastapi import APIRouter, HTTPException
from typing import List
from models import Notificacion, NotificacionCreate, NotificacionUpdate
from database import db

router = APIRouter()


@router.get("/", response_model=List[Notificacion])
def listar_notificaciones(solo_no_leidas: bool = False):
    """Listar notificaciones."""
    notificaciones = db.get_all("notificaciones")
    
    if solo_no_leidas:
        notificaciones = [n for n in notificaciones if not n.get("leida")]
    
    return sorted(notificaciones, key=lambda x: x.get("timestamp", ""), reverse=True)


@router.get("/no-leidas/count")
def contar_no_leidas():
    """Contar notificaciones no leídas."""
    notificaciones = db.get_all("notificaciones")
    no_leidas = [n for n in notificaciones if not n.get("leida")]
    return {"count": len(no_leidas)}


@router.post("/", response_model=Notificacion)
def crear_notificacion(notificacion: NotificacionCreate):
    """Crear nueva notificación."""
    return db.create("notificaciones", notificacion.model_dump())


@router.put("/{notificacion_id}/leer")
def marcar_como_leida(notificacion_id: str):
    """Marcar notificación como leída."""
    existing = db.get_by_id("notificaciones", notificacion_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    
    updated = db.update("notificaciones", notificacion_id, {"leida": True})
    return updated


@router.put("/leer-todas")
def marcar_todas_leidas():
    """Marcar todas las notificaciones como leídas."""
    notificaciones = db.get_all("notificaciones")
    for n in notificaciones:
        if not n.get("leida"):
            db.update("notificaciones", n["id"], {"leida": True})
    
    return {"success": True, "message": "Todas las notificaciones marcadas como leídas"}


@router.delete("/{notificacion_id}")
def eliminar_notificacion(notificacion_id: str):
    """Eliminar notificación."""
    existing = db.get_by_id("notificaciones", notificacion_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    
    db.delete("notificaciones", notificacion_id)
    return {"success": True, "message": "Notificación eliminada"}
