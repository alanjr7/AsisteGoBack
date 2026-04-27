"""Router para gestión de repuestos - Usando PostgreSQL."""
import json
import uuid
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Repuesto, RepuestoCreate, RepuestoUpdate
from database_sql import get_db, Repuesto as RepuestoDB
from utils.security import get_taller_id_from_token

router = APIRouter()


def get_current_taller_id(authorization: str = Header(None)) -> Optional[str]:
    """Extraer taller_id del token JWT."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return get_taller_id_from_token(token)


def _repuesto_to_dict(r: RepuestoDB) -> dict:
    """Convertir modelo SQL a dict para respuesta API."""
    return {
        "id": r.id,
        "nombre": r.nombre,
        "descripcion": r.descripcion,
        "precio": r.precio,
        "imagen": r.imagen,
        "disponible": r.disponible,
        "marca": r.marca,
        "categoria": r.categoria,
        "vehiculos_compatibles": json.loads(r.vehiculos_compatibles) if r.vehiculos_compatibles else [],
        "stock": r.stock,
        "stock_minimo": r.stock_minimo,
        "taller_id": r.taller_id,
        "taller_nombre": r.taller.nombre if r.taller else "Taller Desconocido",
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/", response_model=List[Repuesto])
def listar_repuestos(
    categoria: Optional[str] = None,
    disponible: Optional[bool] = None,
    q: Optional[str] = None,
    stock_bajo: bool = False,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Listar repuestos. Los talleres ven solo lo suyo, los clientes ven todo."""
    taller_id = None
    tipo_usuario = None
    
    if authorization:
        try:
            token = authorization.replace("Bearer ", "")
            payload = decode_access_token(token)
            if payload:
                taller_id = payload.get("taller_id")
                tipo_usuario = payload.get("tipo_usuario")
        except:
            pass
    
    query = db.query(RepuestoDB)
    
    # Filtrado por taller: solo si el usuario es de tipo 'taller'
    if tipo_usuario == "taller" and taller_id:
        query = query.filter(RepuestoDB.taller_id == taller_id)
    
    if categoria:
        query = query.filter(RepuestoDB.categoria == categoria)
    
    if disponible is not None:
        query = query.filter(RepuestoDB.disponible == disponible)
    
    if stock_bajo:
        query = query.filter(RepuestoDB.stock <= RepuestoDB.stock_minimo)
    
    if q:
        q_lower = f"%{q.lower()}%"
        query = query.filter(
            func.lower(RepuestoDB.nombre).like(q_lower) |
            func.lower(RepuestoDB.descripcion).like(q_lower)
        )
    
    return [_repuesto_to_dict(r) for r in query.all()]


@router.get("/{repuesto_id}", response_model=Repuesto)
def obtener_repuesto(repuesto_id: str, db: Session = Depends(get_db)):
    """Obtener repuesto por ID."""
    repuesto = db.query(RepuestoDB).filter(RepuestoDB.id == repuesto_id).first()
    if not repuesto:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    return _repuesto_to_dict(repuesto)


@router.post("/", response_model=Repuesto)
def crear_repuesto(
    repuesto: RepuestoCreate,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Crear nuevo repuesto en el taller del usuario."""
    taller_id = get_current_taller_id(authorization)
    if not taller_id:
        raise HTTPException(status_code=403, detail="Usuario no tiene un taller asignado")
    
    data = repuesto.model_dump()
    
    nuevo = RepuestoDB(
        id=str(uuid.uuid4()),
        taller_id=taller_id,
        nombre=data["nombre"],
        descripcion=data.get("descripcion"),
        precio=data["precio"],
        imagen=data.get("imagen"),
        disponible=data.get("disponible", True),
        marca=data.get("marca"),
        categoria=data.get("categoria"),
        vehiculos_compatibles=json.dumps(data.get("vehiculos_compatibles", [])),
        stock=data.get("stock", 0),
        stock_minimo=data.get("stock_minimo", 5),
    )
    
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return _repuesto_to_dict(nuevo)


@router.put("/{repuesto_id}", response_model=Repuesto)
def actualizar_repuesto(repuesto_id: str, repuesto: RepuestoUpdate, db: Session = Depends(get_db)):
    """Actualizar repuesto."""
    existing = db.query(RepuestoDB).filter(RepuestoDB.id == repuesto_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    
    update_data = repuesto.model_dump(exclude_unset=True)
    
    # Convertir vehiculos_compatibles a JSON si está presente
    if "vehiculos_compatibles" in update_data:
        update_data["vehiculos_compatibles"] = json.dumps(update_data["vehiculos_compatibles"])
    
    for key, value in update_data.items():
        if hasattr(existing, key):
            setattr(existing, key, value)
    
    db.commit()
    db.refresh(existing)
    return _repuesto_to_dict(existing)


@router.delete("/{repuesto_id}")
def eliminar_repuesto(repuesto_id: str, db: Session = Depends(get_db)):
    """Eliminar repuesto."""
    existing = db.query(RepuestoDB).filter(RepuestoDB.id == repuesto_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    
    db.delete(existing)
    db.commit()
    return {"success": True, "message": "Repuesto eliminado"}


@router.get("/categoria/{categoria}")
def repuestos_por_categoria(categoria: str, db: Session = Depends(get_db)):
    """Filtrar repuestos por categoría."""
    repuestos = db.query(RepuestoDB).filter(RepuestoDB.categoria == categoria).all()
    return [_repuesto_to_dict(r) for r in repuestos]


@router.get("/stats/inventario")
def estadisticas_inventario(db: Session = Depends(get_db)):
    """Obtener estadísticas del inventario."""
    total = db.query(RepuestoDB).count()
    disponibles = db.query(RepuestoDB).filter(RepuestoDB.disponible == True).count()
    stock_bajo = db.query(RepuestoDB).filter(RepuestoDB.stock <= RepuestoDB.stock_minimo).count()
    
    # Valor total del inventario
    valor_total = db.query(func.sum(RepuestoDB.precio * RepuestoDB.stock)).scalar() or 0
    
    # Por categoría
    categorias = db.query(RepuestoDB.categoria, func.count(RepuestoDB.id)).group_by(RepuestoDB.categoria).all()
    
    return {
        "total_repuestos": total,
        "disponibles": disponibles,
        "no_disponibles": total - disponibles,
        "stock_bajo": stock_bajo,
        "valor_total_inventario": valor_total,
        "por_categoria": {cat: count for cat, count in categorias if cat},
    }


@router.put("/{repuesto_id}/stock")
def actualizar_stock(repuesto_id: str, cantidad: int, db: Session = Depends(get_db)):
    """Actualizar stock de un repuesto (incremento/decremento)."""
    repuesto = db.query(RepuestoDB).filter(RepuestoDB.id == repuesto_id).first()
    if not repuesto:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    
    repuesto.stock += cantidad
    if repuesto.stock < 0:
        repuesto.stock = 0
    
    # Actualizar disponibilidad automáticamente
    repuesto.disponible = repuesto.stock > 0
    
    db.commit()
    db.refresh(repuesto)
    
    return {
        "success": True,
        "message": f"Stock actualizado: {repuesto.stock}",
        "repuesto": _repuesto_to_dict(repuesto)
    }
