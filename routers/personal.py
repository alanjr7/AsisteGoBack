from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from models import Personal, PersonalCreate, PersonalUpdate, EstadoPersonal
from database_sql import get_db, Personal as PersonalDB
from sqlalchemy.orm import Session
from datetime import datetime
from utils.timezone import get_now
import uuid
from utils.security import get_taller_id_from_token
from utils.supabase_storage import ensure_full_url

router = APIRouter()


def get_current_taller_id(authorization: str = Header(None)) -> Optional[str]:
    """Extraer taller_id del token JWT."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return get_taller_id_from_token(token)


def _personal_to_dict(p: PersonalDB) -> dict:
    """Convertir modelo SQL a dict para respuesta API."""
    return {
        "id": p.id,
        "nombre": p.nombre,
        "rol": p.rol,
        "estado": p.estado,
        "foto": ensure_full_url(p.foto),
        "telefono": p.telefono,
        "asistencias_dia": p.asistencias_dia or 0,
        "asistencias_mes": p.asistencias_mes or 0,
        "taller_id": p.taller_id,
    }


@router.get("/", response_model=List[Personal])
def listar_personal(
    estado: Optional[str] = None,
    rol: Optional[str] = None,
    disponibles: bool = False,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Listar personal del taller del usuario autenticado."""
    taller_id = get_current_taller_id(authorization)
    
    query = db.query(PersonalDB)
    
    # Filtrar por taller del usuario
    if taller_id:
        query = query.filter(PersonalDB.taller_id == taller_id)

    if estado:
        query = query.filter(PersonalDB.estado == estado)

    if rol:
        query = query.filter(PersonalDB.rol == rol)

    if disponibles:
        query = query.filter(PersonalDB.estado == "disponible")

    return [_personal_to_dict(p) for p in query.all()]


@router.get("/{personal_id}", response_model=Personal)
def obtener_personal(personal_id: str, db: Session = Depends(get_db)):
    """Obtener empleado por ID."""
    empleado = db.query(PersonalDB).filter(PersonalDB.id == personal_id).first()
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return _personal_to_dict(empleado)


@router.post("/", response_model=Personal)
def crear_personal(
    empleado: PersonalCreate,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Crear nuevo empleado en el taller del usuario."""
    taller_id = get_current_taller_id(authorization)
    if not taller_id:
        raise HTTPException(status_code=403, detail="Usuario no tiene un taller asignado")
    
    nuevo = PersonalDB(
        taller_id=taller_id,
        id=str(uuid.uuid4()),
        nombre=empleado.nombre,
        rol=empleado.rol,
        estado=empleado.estado or "disponible",
        foto=empleado.foto,
        telefono=empleado.telefono,
        asistencias_dia=empleado.asistencias_dia or 0,
        asistencias_mes=empleado.asistencias_mes or 0,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _personal_to_dict(nuevo)


@router.put("/{personal_id}", response_model=Personal)
def actualizar_personal(personal_id: str, empleado: PersonalUpdate, db: Session = Depends(get_db)):
    """Actualizar empleado."""
    existing = db.query(PersonalDB).filter(PersonalDB.id == personal_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    data = empleado.model_dump(exclude_unset=True)
    for key, value in data.items():
        if hasattr(existing, key):
            setattr(existing, key, value)

    existing.updated_at = get_now()
    db.commit()
    db.refresh(existing)
    return _personal_to_dict(existing)


@router.put("/{personal_id}/estado")
def cambiar_estado_personal(personal_id: str, estado: str, db: Session = Depends(get_db)):
    """Cambiar estado del empleado."""
    existing = db.query(PersonalDB).filter(PersonalDB.id == personal_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    existing.estado = estado
    existing.updated_at = get_now()
    db.commit()
    db.refresh(existing)
    return _personal_to_dict(existing)


@router.get("/{personal_id}/stats")
def estadisticas_personal(personal_id: str, db: Session = Depends(get_db)):
    """Obtener estadísticas del empleado."""
    empleado = db.query(PersonalDB).filter(PersonalDB.id == personal_id).first()
    if not empleado:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    return {
        "asistencias_dia": empleado.asistencias_dia or 0,
        "asistencias_mes": empleado.asistencias_mes or 0,
        "nombre": empleado.nombre,
        "rol": empleado.rol
    }


@router.delete("/{personal_id}")
def eliminar_personal(personal_id: str, db: Session = Depends(get_db)):
    """Eliminar empleado."""
    existing = db.query(PersonalDB).filter(PersonalDB.id == personal_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    db.delete(existing)
    db.commit()
    return {"success": True, "message": "Empleado eliminado"}
