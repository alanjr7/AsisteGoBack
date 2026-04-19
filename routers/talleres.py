"""Router para gestión de talleres mecánicos."""
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
import uuid

from database_sql import get_db, Taller, User, Personal, Solicitud, Repuesto
from models import Taller as TallerModel, TallerCreate, TallerUpdate
from utils.security import decode_access_token

router = APIRouter(prefix="/talleres", tags=["talleres"])


def get_current_user_from_token(authorization: str, db: Session):
    """Extraer usuario actual del token JWT."""
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


@router.get("/", response_model=List[TallerModel])
def listar_talleres(
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Listar todos los talleres (solo para administradores)."""
    user = get_current_user_from_token(authorization, db)
    if not user or user.rol != "administrador":
        raise HTTPException(status_code=403, detail="Solo administradores pueden listar todos los talleres")
    
    talleres = db.query(Taller).all()
    return talleres


@router.get("/mi-taller", response_model=TallerModel)
def obtener_mi_taller(
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Obtener información del taller del usuario actual."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    taller = db.query(Taller).filter(Taller.id == user.taller_id).first()
    if not taller:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    
    return taller


@router.put("/mi-taller", response_model=TallerModel)
def actualizar_mi_taller(
    data: TallerUpdate,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Actualizar información del taller del usuario actual."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    taller = db.query(Taller).filter(Taller.id == user.taller_id).first()
    if not taller:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    
    # Actualizar campos
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(taller, field, value)
    
    db.commit()
    db.refresh(taller)
    return taller


@router.get("/mi-taller/usuarios")
def listar_usuarios_mi_taller(
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Listar usuarios del taller actual."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    usuarios = db.query(User).filter(User.taller_id == user.taller_id).all()
    return [
        {
            "id": u.id,
            "nombre": u.nombre,
            "email": u.email,
            "rol": u.rol,
            "created_at": u.created_at
        }
        for u in usuarios
    ]


@router.get("/mi-taller/personal")
def listar_personal_mi_taller(
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Listar personal del taller actual."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    personal = db.query(Personal).filter(Personal.taller_id == user.taller_id).all()
    return personal


@router.get("/mi-taller/stats")
def estadisticas_mi_taller(
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Obtener estadísticas del taller actual."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not user.taller_id:
        raise HTTPException(status_code=404, detail="Usuario no tiene un taller asignado")
    
    taller_id = user.taller_id
    
    # Contar solicitudes
    total_solicitudes = db.query(Solicitud).filter(Solicitud.taller_id == taller_id).count()
    solicitudes_pendientes = db.query(Solicitud).filter(
        Solicitud.taller_id == taller_id,
        Solicitud.estado == "pendiente"
    ).count()
    solicitudes_activas = db.query(Solicitud).filter(
        Solicitud.taller_id == taller_id,
        Solicitud.estado.in_(["aceptada", "en_camino", "reparando"])
    ).count()
    solicitudes_finalizadas = db.query(Solicitud).filter(
        Solicitud.taller_id == taller_id,
        Solicitud.estado == "finalizada"
    ).count()
    
    # Contar personal
    total_personal = db.query(Personal).filter(Personal.taller_id == taller_id).count()
    personal_disponible = db.query(Personal).filter(
        Personal.taller_id == taller_id,
        Personal.estado == "disponible"
    ).count()
    
    # Contar repuestos
    total_repuestos = db.query(Repuesto).filter(Repuesto.taller_id == taller_id).count()
    repuestos_disponibles = db.query(Repuesto).filter(
        Repuesto.taller_id == taller_id,
        Repuesto.disponible == True
    ).count()
    
    return {
        "solicitudes": {
            "total": total_solicitudes,
            "pendientes": solicitudes_pendientes,
            "activas": solicitudes_activas,
            "finalizadas": solicitudes_finalizadas
        },
        "personal": {
            "total": total_personal,
            "disponible": personal_disponible
        },
        "repuestos": {
            "total": total_repuestos,
            "disponibles": repuestos_disponibles
        }
    }
