from fastapi import APIRouter, HTTPException, Request, Header, Depends
from typing import List, Optional
from pydantic import BaseModel
from models import MensajeChat, MensajeChatCreate
from database import db as memory_db
from database_sql import get_db, Solicitud as SolicitudDB
from sqlalchemy.orm import Session
from datetime import datetime
from utils.timezone import get_now
from utils.gemini_client import get_gemini_client
from utils.rate_limiter import limiter, IA_RATE_LIMIT
from utils.security import get_taller_id_from_token
from utils.supabase_storage import ensure_full_url

router = APIRouter()


def get_current_taller_id(authorization: str = Header(None)) -> Optional[str]:
    """Extraer taller_id del token JWT."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return get_taller_id_from_token(token)


def verificar_acceso_solicitud(solicitud_id: str, taller_id: Optional[str], db: Session):
    """Verificar que el taller tenga acceso a la solicitud."""
    if not taller_id:
        return True  # Admin o sin taller puede ver todo
    
    solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not solicitud:
        return False
    
    return solicitud.taller_id == taller_id


class ConsultaIARequest(BaseModel):
    """Request para consultar al asistente de IA."""
    mensaje: str
    solicitud_id: Optional[str] = None


class ConsultaIAResponse(BaseModel):
    """Response del asistente de IA."""
    respuesta: str
    sugerencias: List[str] = []
    modelo_usado: str = ""
    tokens_usados: int = 0


@router.get("/{solicitud_id}", response_model=List[MensajeChat])
def obtener_mensajes(
    solicitud_id: str,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Obtener mensajes de chat de una solicitud del taller."""
    taller_id = get_current_taller_id(authorization)
    
    # Validar que la solicitud existe y pertenece al taller
    if not verificar_acceso_solicitud(solicitud_id, taller_id, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta conversación")
    
    # Validar solicitud existe en memoria
    solicitud = memory_db.get_by_id("solicitudes", solicitud_id)
    if not solicitud:
        # Si no está en memoria pero sí en DB, permitir (mensajes vacíos)
        pass
    
    mensajes = memory_db.mensajes_chat.get(solicitud_id, [])
    
    # Asegurar URLs completas
    for m in mensajes:
        if m.get("imagen"):
            m["imagen"] = ensure_full_url(m["imagen"])
        if m.get("audio"):
            m["audio"] = ensure_full_url(m["audio"])
            
    return sorted(mensajes, key=lambda x: x.get("timestamp", ""))


@router.post("/{solicitud_id}")
def enviar_mensaje(
    solicitud_id: str,
    mensaje: MensajeChatCreate,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Enviar mensaje en chat de una solicitud del taller."""
    taller_id = get_current_taller_id(authorization)
    
    # Validar que la solicitud existe y pertenece al taller
    if not verificar_acceso_solicitud(solicitud_id, taller_id, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta conversación")
    
    data = mensaje.model_dump()
    data["id"] = memory_db.generate_id()
    data["timestamp"] = get_now().isoformat()
    
    if solicitud_id not in memory_db.mensajes_chat:
        memory_db.mensajes_chat[solicitud_id] = []
    
    memory_db.mensajes_chat[solicitud_id].append(data)
    return data


@router.put("/{solicitud_id}/leer")
def marcar_mensajes_leidos(
    solicitud_id: str,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Marcar todos los mensajes como leídos."""
    taller_id = get_current_taller_id(authorization)
    
    # Validar que la solicitud existe y pertenece al taller
    if not verificar_acceso_solicitud(solicitud_id, taller_id, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta conversación")

    return {"success": True, "message": "Mensajes marcados como leídos"}


@router.post("/ia/consultar", response_model=ConsultaIAResponse)
@limiter.limit(IA_RATE_LIMIT)
def consultar_ia(request: Request, data: ConsultaIARequest):
    """
    Consultar al asistente de IA de Asistego.
    Útil para preguntas frecuentes, información de servicios, etc.
    Rate limit: 10 requests por minuto por IP.
    """
    try:
        client = get_gemini_client()

        # Construir contexto si hay solicitud_id
        contexto = None
        if data.solicitud_id:
            solicitud = db.get_by_id("solicitudes", data.solicitud_id)
            if solicitud:
                contexto = {
                    "problema": solicitud.get("problema"),
                    "estado": solicitud.get("estado"),
                    "vehiculo": solicitud.get("vehiculo"),
                }

        resultado = client.consultar_chat(data.mensaje, contexto)

        if resultado["success"]:
            return ConsultaIAResponse(
                respuesta=resultado["respuesta"],
                sugerencias=[
                    "¿Cuál es el tiempo estimado de llegada?",
                    "¿Cuánto cuesta el servicio?",
                    "¿Qué debo hacer mientras llega el mecánico?",
                ],
                modelo_usado=resultado.get("modelo_usado", "unknown"),
                tokens_usados=resultado.get("tokens_usados", 0),
            )
        else:
            raise HTTPException(
                status_code=503,
                detail=f"Error del servicio de IA: {resultado.get('error')}"
            )

    except ValueError as e:
        # API key no configurada
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )
