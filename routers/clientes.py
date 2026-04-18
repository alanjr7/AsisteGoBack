from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from models import Cliente, ClienteCreate, ClienteUpdate
from database_sql import get_db, Cliente as ClienteDB
from sqlalchemy.orm import Session
import uuid

router = APIRouter()


def _cliente_to_dict(c: ClienteDB) -> dict:
    """Convertir modelo SQL a dict para respuesta API."""
    return {
        "id": c.id,
        "nombre": c.nombre,
        "telefono": c.telefono,
        "email": c.email,
        "foto": c.foto,
        "lat": c.lat,
        "lng": c.lng,
        "veces_atendido": c.veces_atendido,
        "calificacion_promedio": c.calificacion_promedio,
    }


@router.get("/", response_model=List[Cliente])
def listar_clientes(db: Session = Depends(get_db)):
    """Listar todos los clientes."""
    return [_cliente_to_dict(c) for c in db.query(ClienteDB).all()]


@router.get("/{cliente_id}", response_model=Cliente)
def obtener_cliente(cliente_id: str, db: Session = Depends(get_db)):
    """Obtener cliente por ID."""
    cliente = db.query(ClienteDB).filter(ClienteDB.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return _cliente_to_dict(cliente)


@router.post("/", response_model=Cliente)
def crear_cliente(cliente: ClienteCreate, db: Session = Depends(get_db)):
    """Crear nuevo cliente."""
    data = cliente.model_dump()
    data["id"] = str(uuid.uuid4())
    nuevo = ClienteDB(**data)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _cliente_to_dict(nuevo)


@router.put("/{cliente_id}", response_model=Cliente)
def actualizar_cliente(cliente_id: str, cliente: ClienteUpdate, db: Session = Depends(get_db)):
    """Actualizar cliente."""
    existing = db.query(ClienteDB).filter(ClienteDB.id == cliente_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    data = cliente.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(existing, key, value)

    db.commit()
    db.refresh(existing)
    return _cliente_to_dict(existing)


@router.delete("/{cliente_id}")
def eliminar_cliente(cliente_id: str, db: Session = Depends(get_db)):
    """Eliminar cliente."""
    existing = db.query(ClienteDB).filter(ClienteDB.id == cliente_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    db.delete(existing)
    db.commit()
    return {"success": True, "message": "Cliente eliminado"}


@router.get("/{cliente_id}/servicios")
def servicios_cliente(cliente_id: str, db: Session = Depends(get_db)):
    """Obtener historial de servicios del cliente."""
    cliente = db.query(ClienteDB).filter(ClienteDB.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # TODO: Implementar cuando servicios se migre a MySQL
    return []


@router.get("/mine/by-email")
def obtener_cliente_por_email(email: str, db: Session = Depends(get_db)):
    """Obtener cliente por email (para vincular con usuario autenticado).
    Si no existe, lo crea automáticamente."""
    cliente = db.query(ClienteDB).filter(ClienteDB.email == email).first()
    if not cliente:
        # Auto-crear cliente para usuarios existentes sin cliente
        import uuid
        cliente_id = str(uuid.uuid4())
        nuevo_cliente = ClienteDB(
            id=cliente_id,
            nombre=email.split('@')[0],  # Usar parte del email como nombre temporal
            telefono="",
            email=email,
            foto=None,
            lat=0.0,
            lng=0.0,
            veces_atendido=0,
            calificacion_promedio=None
        )
        db.add(nuevo_cliente)
        db.commit()
        db.refresh(nuevo_cliente)
        return _cliente_to_dict(nuevo_cliente)
    return _cliente_to_dict(cliente)
