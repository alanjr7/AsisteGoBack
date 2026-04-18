from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from models import Repuesto, RepuestoCreate, RepuestoUpdate
from database import db

router = APIRouter()


@router.get("/", response_model=List[Repuesto])
def listar_repuestos(
    categoria: Optional[str] = None,
    disponible: Optional[bool] = None,
    q: Optional[str] = None
):
    """Listar repuestos con filtros."""
    repuestos = db.get_all("repuestos")
    
    if categoria:
        repuestos = [r for r in repuestos if r.get("categoria") == categoria]
    
    if disponible is not None:
        repuestos = [r for r in repuestos if r.get("disponible") == disponible]
    
    if q:
        q_lower = q.lower()
        repuestos = [
            r for r in repuestos
            if q_lower in r.get("nombre", "").lower() or
               q_lower in r.get("descripcion", "").lower()
        ]
    
    return repuestos


@router.get("/{repuesto_id}", response_model=Repuesto)
def obtener_repuesto(repuesto_id: str):
    """Obtener repuesto por ID."""
    repuesto = db.get_by_id("repuestos", repuesto_id)
    if not repuesto:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    return repuesto


@router.post("/", response_model=Repuesto)
def crear_repuesto(repuesto: RepuestoCreate):
    """Crear nuevo repuesto."""
    return db.create("repuestos", repuesto.model_dump())


@router.put("/{repuesto_id}", response_model=Repuesto)
def actualizar_repuesto(repuesto_id: str, repuesto: RepuestoUpdate):
    """Actualizar repuesto."""
    existing = db.get_by_id("repuestos", repuesto_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    
    updated = db.update("repuestos", repuesto_id, repuesto.model_dump(exclude_unset=True))
    return updated


@router.delete("/{repuesto_id}")
def eliminar_repuesto(repuesto_id: str):
    """Eliminar repuesto."""
    existing = db.get_by_id("repuestos", repuesto_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    
    db.delete("repuestos", repuesto_id)
    return {"success": True, "message": "Repuesto eliminado"}


@router.get("/categoria/{categoria}")
def repuestos_por_categoria(categoria: str):
    """Filtrar repuestos por categoría."""
    repuestos = db.get_all("repuestos")
    return [r for r in repuestos if r.get("categoria") == categoria]
