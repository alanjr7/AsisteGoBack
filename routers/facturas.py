from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from models import Factura, FacturaUpdate
from database_sql import get_db, Factura as FacturaDB, Solicitud, Cliente
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

router = APIRouter()


class FacturaCreateRequest(BaseModel):
    """Request para crear factura desde la app."""
    solicitud_id: str
    cliente_id: str
    monto: float
    metodo_pago: str  # qr, tarjeta, efectivo
    items: Optional[list] = None


def _factura_to_dict(f: FacturaDB) -> dict:
    """Convertir modelo SQL a dict para respuesta API."""
    return {
        "id": f.id,
        "solicitud_id": f.solicitud_id,
        "cliente_id": f.cliente_id,
        "cliente": {
            "id": f.cliente.id,
            "nombre": f.cliente.nombre,
            "telefono": f.cliente.telefono,
            "email": f.cliente.email,
            "foto": f.cliente.foto,
        } if f.cliente else None,
        "monto": f.monto,
        "comision": f.comision,
        "total": f.total,
        "metodo_pago": f.metodo_pago,
        "comprobante": f.comprobante,
        "enviada": f.enviada,
        "fecha": f.created_at.isoformat() if f.created_at else None,
    }


@router.get("/", response_model=List[Factura])
def listar_facturas(db: Session = Depends(get_db)):
    """Listar todas las facturas."""
    facturas = db.query(FacturaDB).all()
    return [_factura_to_dict(f) for f in facturas]


@router.get("/{factura_id}", response_model=Factura)
def obtener_factura(factura_id: str, db: Session = Depends(get_db)):
    """Obtener factura por ID."""
    factura = db.query(FacturaDB).filter(FacturaDB.id == factura_id).first()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return _factura_to_dict(factura)


@router.post("/", response_model=Factura)
def crear_factura(data: FacturaCreateRequest, db: Session = Depends(get_db)):
    """Crear nueva factura desde la app del cliente."""
    # Validar que la solicitud existe
    solicitud = db.query(Solicitud).filter(Solicitud.id == data.solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Validar cliente (usar el de la solicitud o el proporcionado)
    cliente_id = data.cliente_id or solicitud.cliente_id
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Calcular comisión (10%) y total
    comision = data.monto * 0.10
    total = data.monto + comision
    
    # Crear factura en SQL
    nueva = FacturaDB(
        id=str(uuid.uuid4()),
        solicitud_id=data.solicitud_id,
        cliente_id=cliente_id,
        monto=data.monto,
        comision=comision,
        total=total,
        metodo_pago=data.metodo_pago,
        comprobante=None,
        enviada=False,
    )
    
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    
    return _factura_to_dict(nueva)


@router.put("/{factura_id}", response_model=Factura)
def actualizar_factura(factura_id: str, factura: FacturaUpdate, db: Session = Depends(get_db)):
    """Actualizar factura."""
    existing = db.query(FacturaDB).filter(FacturaDB.id == factura_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    update_data = factura.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(existing, key):
            setattr(existing, key, value)
    
    existing.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(existing)
    return _factura_to_dict(existing)


@router.put("/{factura_id}/enviar")
def enviar_factura(factura_id: str, db: Session = Depends(get_db)):
    """Marcar factura como enviada."""
    existing = db.query(FacturaDB).filter(FacturaDB.id == factura_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    
    existing.enviada = True
    existing.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Factura marcada como enviada"}


@router.get("/solicitud/{solicitud_id}/estado")
def verificar_estado_pago(solicitud_id: str, db: Session = Depends(get_db)):
    """Verificar si una solicitud tiene factura pagada."""
    factura = db.query(FacturaDB).filter(
        FacturaDB.solicitud_id == solicitud_id
    ).first()
    
    if not factura:
        return {
            "solicitud_id": solicitud_id,
            "tiene_factura": False,
            "pagado": False,
            "factura_id": None
        }
    
    return {
        "solicitud_id": solicitud_id,
        "tiene_factura": True,
        "pagado": factura.enviada,
        "factura_id": factura.id,
        "monto": factura.monto,
        "total": factura.total
    }


@router.get("/stats/diarias")
def estadisticas_diarias(db: Session = Depends(get_db)):
    """Obtener estadísticas de facturas del día actual."""
    from datetime import date
    
    hoy = date.today()
    facturas_hoy = db.query(FacturaDB).filter(
        FacturaDB.enviada == True
    ).all()
    
    # Filtrar por fecha manualmente (SQLite/MySQL compatible)
    facturas_hoy = [f for f in facturas_hoy if f.created_at and f.created_at.date() == hoy]
    
    total_facturas = len(facturas_hoy)
    ingresos_hoy = sum(f.monto for f in facturas_hoy)
    comisiones_hoy = sum(f.comision for f in facturas_hoy)
    totales_hoy = sum(f.total for f in facturas_hoy)
    
    return {
        "fecha": hoy.isoformat(),
        "total_facturas_hoy": total_facturas,
        "ingresos_hoy": ingresos_hoy,
        "comisiones_hoy": comisiones_hoy,
        "total_con_comision_hoy": totales_hoy
    }


@router.get("/stats/resumen")
def estadisticas_facturas(db: Session = Depends(get_db)):
    """Obtener estadísticas de facturas."""
    facturas = db.query(FacturaDB).all()
    
    total = len(facturas)
    ingresos = sum(f.monto for f in facturas)
    comisiones = sum(f.comision for f in facturas)
    totales = sum(f.total for f in facturas)
    enviadas = len([f for f in facturas if f.enviada])
    
    return {
        "total_facturas": total,
        "facturas_enviadas": enviadas,
        "ingresos_totales": ingresos,
        "comisiones_totales": comisiones,
        "total_con_comision": totales
    }
