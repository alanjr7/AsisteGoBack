"""Router para gestión de vehículos de clientes."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from database_sql import get_db, Vehiculo as VehiculoDB, Cliente

router = APIRouter()


class VehiculoBase(BaseModel):
    """Modelo base para vehículos."""
    marca: str
    modelo: str
    anio: int
    placa: str
    color: str
    tipo: str = "Sedán"


class VehiculoCreate(VehiculoBase):
    """Modelo para crear vehículo."""
    cliente_id: str


class VehiculoUpdate(BaseModel):
    """Modelo para actualizar vehículo."""
    marca: Optional[str] = None
    modelo: Optional[str] = None
    anio: Optional[int] = None
    placa: Optional[str] = None
    color: Optional[str] = None
    tipo: Optional[str] = None
    activo: Optional[bool] = None


class Vehiculo(VehiculoBase):
    """Modelo completo de vehículo."""
    id: str
    cliente_id: str
    activo: bool

    class Config:
        from_attributes = True


def _vehiculo_to_dict(v: VehiculoDB) -> dict:
    """Convertir modelo SQL a dict para respuesta API."""
    return {
        "id": v.id,
        "cliente_id": v.cliente_id,
        "marca": v.marca,
        "modelo": v.modelo,
        "anio": v.anio,
        "placa": v.placa,
        "color": v.color,
        "tipo": v.tipo,
        "activo": v.activo,
    }


@router.get("/", response_model=List[Vehiculo])
def listar_vehiculos(
    cliente_id: Optional[str] = None,
    activo: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Listar vehículos con filtros opcionales."""
    query = db.query(VehiculoDB)

    if cliente_id:
        query = query.filter(VehiculoDB.cliente_id == cliente_id)

    if activo is not None:
        query = query.filter(VehiculoDB.activo == activo)

    return [_vehiculo_to_dict(v) for v in query.all()]


@router.get("/cliente/{cliente_id}", response_model=List[Vehiculo])
def listar_vehiculos_por_cliente(cliente_id: str, db: Session = Depends(get_db)):
    """Listar todos los vehículos de un cliente."""
    vehiculos = db.query(VehiculoDB).filter(VehiculoDB.cliente_id == cliente_id).all()
    return [_vehiculo_to_dict(v) for v in vehiculos]


@router.get("/{vehiculo_id}", response_model=Vehiculo)
def obtener_vehiculo(vehiculo_id: str, db: Session = Depends(get_db)):
    """Obtener vehículo por ID."""
    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return _vehiculo_to_dict(vehiculo)


@router.post("/", response_model=Vehiculo)
def crear_vehiculo(vehiculo: VehiculoCreate, db: Session = Depends(get_db)):
    """Crear nuevo vehículo para un cliente."""
    # Verificar que el cliente existe
    cliente = db.query(Cliente).filter(Cliente.id == vehiculo.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Verificar que no exista otra placa igual
    existing = db.query(VehiculoDB).filter(VehiculoDB.placa == vehiculo.placa).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un vehículo con esa placa")

    nuevo = VehiculoDB(
        id=str(uuid.uuid4()),
        cliente_id=vehiculo.cliente_id,
        marca=vehiculo.marca,
        modelo=vehiculo.modelo,
        anio=vehiculo.anio,
        placa=vehiculo.placa,
        color=vehiculo.color,
        tipo=vehiculo.tipo,
        activo=True,
    )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return _vehiculo_to_dict(nuevo)


@router.put("/{vehiculo_id}", response_model=Vehiculo)
def actualizar_vehiculo(vehiculo_id: str, data: VehiculoUpdate, db: Session = Depends(get_db)):
    """Actualizar vehículo."""
    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    # Verificar placa única si se está actualizando
    if "placa" in update_data:
        existing = db.query(VehiculoDB).filter(
            VehiculoDB.placa == update_data["placa"],
            VehiculoDB.id != vehiculo_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe otro vehículo con esa placa")

    for key, value in update_data.items():
        if hasattr(vehiculo, key):
            setattr(vehiculo, key, value)

    db.commit()
    db.refresh(vehiculo)

    return _vehiculo_to_dict(vehiculo)


@router.put("/{vehiculo_id}/activar", response_model=Vehiculo)
def activar_vehiculo(vehiculo_id: str, db: Session = Depends(get_db)):
    """Activar un vehículo y desactivar los demás del mismo cliente."""
    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    # Desactivar todos los vehículos del cliente
    db.query(VehiculoDB).filter(
        VehiculoDB.cliente_id == vehiculo.cliente_id
    ).update({"activo": False})

    # Activar el vehículo seleccionado
    vehiculo.activo = True

    db.commit()
    db.refresh(vehiculo)

    return _vehiculo_to_dict(vehiculo)


@router.delete("/{vehiculo_id}")
def eliminar_vehiculo(vehiculo_id: str, db: Session = Depends(get_db)):
    """Eliminar vehículo."""
    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    db.delete(vehiculo)
    db.commit()

    return {"success": True, "message": "Vehículo eliminado"}
