"""
Router para gestión de pagos entre taller y clientes.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from models import (
    ConfirmarPagoRequest, ProcesarPagoRequest, EstadoPagoResponse,
    EstadoPago, MetodoPago, Factura
)
from database_sql import get_db, Solicitud, Cliente, Factura as FacturaDB
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

# Importar WebSocket
from routers.websocket import notify_pago_confirmado, notify_pago_completado

router = APIRouter()


def _calcular_total(monto: float) -> tuple[float, float]:
    """Calcular comisión (10%) y total."""
    comision = monto * 0.10
    total = monto + comision
    return comision, total


@router.post("/confirmar", response_model=dict)
async def confirmar_pago(data: ConfirmarPagoRequest, db: Session = Depends(get_db)):
    """
    El taller confirma el monto a cobrar por un servicio.
    Esto notifica al cliente que puede proceder al pago.
    """
    # Validar que la solicitud existe
    solicitud = db.query(Solicitud).filter(Solicitud.id == data.solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Validar que la solicitud está finalizada
    if solicitud.estado.value != "finalizada":
        raise HTTPException(
            status_code=400, 
            detail=f"La solicitud debe estar finalizada para confirmar pago. Estado actual: {solicitud.estado.value}"
        )
    
    # Validar monto
    if data.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    
    # Calcular comisión y total
    comision, total = _calcular_total(data.monto)
    
    # Actualizar solicitud con estado de pago
    solicitud.estado_pago = "confirmado"
    solicitud.monto_pago = data.monto
    solicitud.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(solicitud)
    
    # Notificar al cliente vía WebSocket
    await notify_pago_confirmado(
        cliente_id=solicitud.cliente_id,
        solicitud_id=data.solicitud_id,
        monto=data.monto,
        comision=comision,
        total=total
    )
    
    return {
        "success": True,
        "message": "Monto confirmado. Cliente notificado.",
        "solicitud_id": data.solicitud_id,
        "monto": data.monto,
        "comision": comision,
        "total": total,
        "estado_pago": "confirmado"
    }


@router.get("/solicitud/{solicitud_id}/estado", response_model=dict)
def verificar_estado_pago(solicitud_id: str, db: Session = Depends(get_db)):
    """
    Verificar el estado de pago de una solicitud.
    Usado por el mobile para saber si hay un monto confirmado.
    """
    solicitud = db.query(Solicitud).filter(Solicitud.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Verificar si ya existe una factura pagada
    factura = db.query(FacturaDB).filter(
        FacturaDB.solicitud_id == solicitud_id,
        FacturaDB.enviada == True
    ).first()
    
    estado_pago = solicitud.estado_pago or "pendiente"
    monto = solicitud.monto_pago
    
    comision, total = (0, 0) if not monto else _calcular_total(monto)
    
    return {
        "solicitud_id": solicitud_id,
        "estado_pago": estado_pago,
        "monto": monto,
        "comision": comision if monto else None,
        "total": total if monto else None,
        "tiene_factura": factura is not None,
        "factura_id": factura.id if factura else None,
        "pagado": factura is not None and factura.enviada
    }


@router.post("/procesar", response_model=dict)
async def procesar_pago(data: ProcesarPagoRequest, db: Session = Depends(get_db)):
    """
    El cliente procesa el pago.
    Crea una factura y marca el pago como completado.
    """
    # Validar solicitud
    solicitud = db.query(Solicitud).filter(Solicitud.id == data.solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Validar que hay un monto confirmado
    if not solicitud.monto_pago or solicitud.estado_pago != "confirmado":
        raise HTTPException(
            status_code=400, 
            detail="No hay un monto confirmado para esta solicitud"
        )
    
    # Validar que no esté ya pagada
    factura_existente = db.query(FacturaDB).filter(
        FacturaDB.solicitud_id == data.solicitud_id,
        FacturaDB.enviada == True
    ).first()
    
    if factura_existente:
        raise HTTPException(status_code=400, detail="Esta solicitud ya ha sido pagada")
    
    # Calcular comisión y total
    monto = solicitud.monto_pago
    comision, total = _calcular_total(monto)
    
    # Crear factura
    nueva_factura = FacturaDB(
        id=str(uuid.uuid4()),
        solicitud_id=data.solicitud_id,
        cliente_id=solicitud.cliente_id,
        monto=monto,
        comision=comision,
        total=total,
        metodo_pago=data.metodo_pago.value,
        comprobante=data.comprobante,
        enviada=True,  # Marcar como enviada/pagada inmediatamente
    )
    
    db.add(nueva_factura)
    
    # Actualizar estado de pago de la solicitud
    solicitud.estado_pago = "completado"
    solicitud.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(nueva_factura)
    
    # Notificar al taller que el pago fue completado
    await notify_pago_completado(
        cliente_id=solicitud.cliente_id,
        solicitud_id=data.solicitud_id,
        factura_id=nueva_factura.id,
        monto=monto,
        total=total
    )
    
    return {
        "success": True,
        "message": "Pago procesado exitosamente",
        "factura_id": nueva_factura.id,
        "solicitud_id": data.solicitud_id,
        "monto": monto,
        "comision": comision,
        "total": total,
        "metodo_pago": data.metodo_pago.value,
        "estado_pago": "completado"
    }


@router.get("/cliente/{cliente_id}", response_model=List[dict])
def listar_pagos_cliente(cliente_id: str, db: Session = Depends(get_db)):
    """
    Listar historial de pagos/facturas de un cliente.
    """
    # Verificar cliente existe
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Obtener facturas del cliente
    facturas = db.query(FacturaDB).filter(
        FacturaDB.cliente_id == cliente_id
    ).order_by(FacturaDB.created_at.desc()).all()
    
    resultado = []
    for f in facturas:
        # Obtener información de la solicitud relacionada
        solicitud = db.query(Solicitud).filter(Solicitud.id == f.solicitud_id).first()
        
        resultado.append({
            "factura_id": f.id,
            "solicitud_id": f.solicitud_id,
            "monto": f.monto,
            "comision": f.comision,
            "total": f.total,
            "metodo_pago": f.metodo_pago,
            "estado": "completado" if f.enviada else "pendiente",
            "fecha": f.created_at.isoformat() if f.created_at else None,
            "vehiculo": {
                "marca": solicitud.vehiculo_marca if solicitud else None,
                "modelo": solicitud.vehiculo_modelo if solicitud else None,
                "placa": solicitud.vehiculo_placa if solicitud else None,
            } if solicitud else None
        })
    
    return resultado


@router.get("/taller/pendientes", response_model=List[dict])
def listar_pagos_pendientes(db: Session = Depends(get_db)):
    """
    Listar solicitudes finalizadas que están esperando confirmación de pago o pago.
    """
    from database_sql import EstadoSolicitud
    
    # Solicitudes finalizadas con estado_pago pendiente o confirmado (pero no completado)
    solicitudes = db.query(Solicitud).filter(
        Solicitud.estado == EstadoSolicitud.FINALIZADA,
        Solicitud.estado_pago.in_(["pendiente", "confirmado"])
    ).order_by(Solicitud.created_at.desc()).all()
    
    resultado = []
    for s in solicitudes:
        comision, total = (0, 0) if not s.monto_pago else _calcular_total(s.monto_pago)
        
        resultado.append({
            "solicitud_id": s.id,
            "cliente": {
                "id": s.cliente.id if s.cliente else None,
                "nombre": s.cliente.nombre if s.cliente else None,
                "telefono": s.cliente.telefono if s.cliente else None,
            },
            "vehiculo": {
                "marca": s.vehiculo_marca,
                "modelo": s.vehiculo_modelo,
                "placa": s.vehiculo_placa,
            },
            "estado_pago": s.estado_pago or "pendiente",
            "monto": s.monto_pago,
            "comision": comision if s.monto_pago else None,
            "total": total if s.monto_pago else None,
            "fecha_finalizacion": s.updated_at.isoformat() if s.updated_at else None,
        })
    
    return resultado


@router.get("/taller/resumen", response_model=dict)
def resumen_pagos_taller(db: Session = Depends(get_db)):
    """
    Resumen de pagos para el dashboard del taller.
    """
    from database_sql import EstadoSolicitud
    
    # Contar por estado
    pendientes = db.query(Solicitud).filter(
        Solicitud.estado == EstadoSolicitud.FINALIZADA,
        Solicitud.estado_pago == "pendiente"
    ).count()
    
    confirmados = db.query(Solicitud).filter(
        Solicitud.estado == EstadoSolicitud.FINALIZADA,
        Solicitud.estado_pago == "confirmado"
    ).count()
    
    # Calcular monto total esperado (pagos confirmados no completados)
    confirmados_query = db.query(Solicitud).filter(
        Solicitud.estado == EstadoSolicitud.FINALIZADA,
        Solicitud.estado_pago == "confirmado"
    ).all()
    monto_esperado = sum(s.monto_pago or 0 for s in confirmados_query)
    
    # Calcular ingresos totales (facturas pagadas)
    facturas_pagadas = db.query(FacturaDB).filter(FacturaDB.enviada == True).all()
    ingresos_totales = sum(f.monto for f in facturas_pagadas)
    comisiones_totales = sum(f.comision for f in facturas_pagadas)
    
    return {
        "pendientes_confirmacion": pendientes,
        "esperando_pago": confirmados,
        "monto_esperado": monto_esperado,
        "servicios_pagados": len(facturas_pagadas),
        "ingresos_totales": ingresos_totales,
        "comisiones_totales": comisiones_totales,
        "neto_total": ingresos_totales - comisiones_totales
    }
