from fastapi import APIRouter, HTTPException
from typing import List
from models import MensajeChat, MensajeChatCreate
from database import db
from datetime import datetime

router = APIRouter()


@router.get("/{solicitud_id}", response_model=List[MensajeChat])
def obtener_mensajes(solicitud_id: str):
    """Obtener mensajes de chat de una solicitud."""
    # Validar solicitud existe
    solicitud = db.get_by_id("solicitudes", solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    mensajes = db.mensajes_chat.get(solicitud_id, [])
    return sorted(mensajes, key=lambda x: x.get("timestamp", ""))


@router.post("/{solicitud_id}")
def enviar_mensaje(solicitud_id: str, mensaje: MensajeChatCreate):
    """Enviar mensaje en chat."""
    # Validar solicitud existe
    solicitud = db.get_by_id("solicitudes", solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    data = mensaje.model_dump()
    data["id"] = db.generate_id()
    data["timestamp"] = datetime.now().isoformat()
    
    if solicitud_id not in db.mensajes_chat:
        db.mensajes_chat[solicitud_id] = []
    
    db.mensajes_chat[solicitud_id].append(data)
    return data


@router.put("/{solicitud_id}/leer")
def marcar_mensajes_leidos(solicitud_id: str):
    """Marcar todos los mensajes como leídos."""
    solicitud = db.get_by_id("solicitudes", solicitud_id)
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    return {"success": True, "message": "Mensajes marcados como leídos"}
