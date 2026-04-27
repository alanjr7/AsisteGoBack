"""Router para generación de reportes del sistema."""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime, date, timedelta
from utils.timezone import get_now
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract

from database_sql import get_db, Solicitud, Cliente, Personal, Factura, Vehiculo, EstadoSolicitud
from utils.security import get_taller_id_from_token

router = APIRouter()


def get_current_taller_id(authorization: str = Header(None)) -> Optional[str]:
    """Extraer taller_id del token JWT."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return get_taller_id_from_token(token)


class ReporteFiltros(BaseModel):
    """Filtros para generación de reportes."""
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: Optional[str] = None
    tipo: Optional[str] = None  # solicitudes, pagos, personal, inventario


class ReporteResumen(BaseModel):
    """Resumen de reporte generado."""
    tipo: str
    fecha_generacion: datetime
    periodo: str
    total_registros: int
    datos: dict


def _get_default_dates():
    """Obtener fechas por defecto (último mes)."""
    hoy = date.today()
    inicio = hoy - timedelta(days=30)
    return inicio, hoy


@router.get("/solicitudes", response_model=ReporteResumen)
def reporte_solicitudes(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Generar reporte de solicitudes de servicio del taller."""
    taller_id = get_current_taller_id(authorization)
    
    if not fecha_inicio or not fecha_fin:
        fecha_inicio, fecha_fin = _get_default_dates()

    query = db.query(Solicitud).filter(
        and_(
            func.date(Solicitud.created_at) >= fecha_inicio,
            func.date(Solicitud.created_at) <= fecha_fin
        )
    )
    
    # Filtrar por taller
    if taller_id:
        query = query.filter(Solicitud.taller_id == taller_id)

    if estado:
        try:
            estado_enum = EstadoSolicitud(estado)
            query = query.filter(Solicitud.estado == estado_enum)
        except ValueError:
            pass

    solicitudes = query.all()

    # Estadísticas por estado
    por_estado = {}
    for s in solicitudes:
        est = s.estado.value if hasattr(s.estado, 'value') else str(s.estado)
        por_estado[est] = por_estado.get(est, 0) + 1

    # Estadísticas por tipo de problema
    por_problema = {}
    for s in solicitudes:
        problema = s.problema or "Sin especificar"
        por_problema[problema] = por_problema.get(problema, 0) + 1

    return ReporteResumen(
        tipo="solicitudes",
        fecha_generacion=get_now(),
        periodo=f"{fecha_inicio} a {fecha_fin}",
        total_registros=len(solicitudes),
        datos={
            "por_estado": por_estado,
            "por_problema": por_problema,
            "total_ingresos": sum(s.monto_pago or 0 for s in solicitudes),
            "promedio_distancia": sum(s.distancia or 0 for s in solicitudes) / len(solicitudes) if solicitudes else 0,
            "requirieron_repuestos": sum(1 for s in solicitudes if s.requiere_repuestos),
        }
    )


@router.get("/pagos", response_model=ReporteResumen)
def reporte_pagos(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    metodo_pago: Optional[str] = None,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Generar reporte de pagos/facturación del taller."""
    taller_id = get_current_taller_id(authorization)
    
    if not fecha_inicio or not fecha_fin:
        fecha_inicio, fecha_fin = _get_default_dates()

    query = db.query(Factura).join(Solicitud, Factura.solicitud_id == Solicitud.id)
    
    query = query.filter(
        and_(
            func.date(Factura.created_at) >= fecha_inicio,
            func.date(Factura.created_at) <= fecha_fin
        )
    )
    
    # Filtrar por taller
    if taller_id:
        query = query.filter(Solicitud.taller_id == taller_id)

    if metodo_pago:
        query = query.filter(Factura.metodo_pago == metodo_pago)

    facturas = query.all()

    # Estadísticas por método de pago
    por_metodo = {}
    for f in facturas:
        met = f.metodo_pago or "desconocido"
        por_metodo[met] = por_metodo.get(met, 0) + 1

    return ReporteResumen(
        tipo="pagos",
        fecha_generacion=get_now(),
        periodo=f"{fecha_inicio} a {fecha_fin}",
        total_registros=len(facturas),
        datos={
            "por_metodo": por_metodo,
            "total_monto": sum(f.monto for f in facturas),
            "total_comisiones": sum(f.comision for f in facturas),
            "total_general": sum(f.total for f in facturas),
            "facturas_enviadas": sum(1 for f in facturas if f.enviada),
            "facturas_pendientes": sum(1 for f in facturas if not f.enviada),
            "promedio_monto": sum(f.monto for f in facturas) / len(facturas) if facturas else 0,
        }
    )


@router.get("/personal", response_model=ReporteResumen)
def reporte_personal(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Generar reporte de desempeño del personal del taller."""
    taller_id = get_current_taller_id(authorization)
    
    if not fecha_inicio or not fecha_fin:
        fecha_inicio, fecha_fin = _get_default_dates()

    query = db.query(Personal)
    
    # Filtrar por taller
    if taller_id:
        query = query.filter(Personal.taller_id == taller_id)
    
    personal = query.all()

    # Estadísticas por rol
    por_rol = {}
    for p in personal:
        rol = p.rol or "sin_rol"
        por_rol[rol] = por_rol.get(rol, 0) + 1

    # Estadísticas por estado
    por_estado = {}
    for p in personal:
        est = p.estado or "desconocido"
        por_estado[est] = por_estado.get(est, 0) + 1

    return ReporteResumen(
        tipo="personal",
        fecha_generacion=get_now(),
        periodo=f"{fecha_inicio} a {fecha_fin}",
        total_registros=len(personal),
        datos={
            "por_rol": por_rol,
            "por_estado": por_estado,
            "total_asistencias_dia": sum(p.asistencias_dia or 0 for p in personal),
            "total_asistencias_mes": sum(p.asistencias_mes or 0 for p in personal),
            "personal_activo": sum(1 for p in personal if p.estado == "disponible"),
            "personal_ocupado": sum(1 for p in personal if p.estado == "ocupado"),
            "detalle_personal": [
                {
                    "id": p.id,
                    "nombre": p.nombre,
                    "rol": p.rol,
                    "estado": p.estado,
                    "asistencias_dia": p.asistencias_dia or 0,
                    "asistencias_mes": p.asistencias_mes or 0,
                }
                for p in personal
            ],
        }
    )


@router.get("/clientes", response_model=ReporteResumen)
def reporte_clientes(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Generar reporte de clientes del taller."""
    taller_id = get_current_taller_id(authorization)
    
    if not fecha_inicio or not fecha_fin:
        fecha_inicio, fecha_fin = _get_default_dates()

    # Obtener clientes que tienen solicitudes en este taller
    if taller_id:
        clientes_ids = db.query(Solicitud.cliente_id).filter(
            Solicitud.taller_id == taller_id,
            func.date(Solicitud.created_at) >= fecha_inicio,
            func.date(Solicitud.created_at) <= fecha_fin
        ).distinct().all()
        clientes_ids = [c[0] for c in clientes_ids]
        
        clientes = db.query(Cliente).filter(Cliente.id.in_(clientes_ids)).all() if clientes_ids else []
        todos_clientes = db.query(Cliente).filter(Cliente.id.in_(
            db.query(Solicitud.cliente_id).filter(Solicitud.taller_id == taller_id).distinct()
        )).all()
    else:
        clientes = db.query(Cliente).filter(
            and_(
                func.date(Cliente.created_at) >= fecha_inicio,
                func.date(Cliente.created_at) <= fecha_fin
            )
        ).all()
        todos_clientes = db.query(Cliente).all()

    return ReporteResumen(
        tipo="clientes",
        fecha_generacion=get_now(),
        periodo=f"{fecha_inicio} a {fecha_fin}",
        total_registros=len(clientes),
        datos={
            "total_clientes": len(todos_clientes),
            "nuevos_en_periodo": len(clientes),
            "clientes_recurrentes": sum(1 for c in todos_clientes if (c.veces_atendido or 0) > 1),
            "promedio_servicios_por_cliente": sum(c.veces_atendido or 0 for c in todos_clientes) / len(todos_clientes) if todos_clientes else 0,
            "clientes_con_calificacion": sum(1 for c in todos_clientes if c.calificacion_promedio is not None),
            "calificacion_promedio_general": sum(c.calificacion_promedio or 0 for c in todos_clientes) / sum(1 for c in todos_clientes if c.calificacion_promedio is not None) if any(c.calificacion_promedio for c in todos_clientes) else 0,
        }
    )


@router.get("/dashboard", response_model=dict)
def reporte_dashboard(
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Obtener datos agregados para el dashboard del taller."""
    taller_id = get_current_taller_id(authorization)
    
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    
    # Base queries filtradas por taller
    base_solicitudes = db.query(Solicitud)
    base_personal = db.query(Personal)
    base_facturas = db.query(Factura).join(Solicitud, Factura.solicitud_id == Solicitud.id)
    
    if taller_id:
        base_solicitudes = base_solicitudes.filter(Solicitud.taller_id == taller_id)
        base_personal = base_personal.filter(Personal.taller_id == taller_id)
        base_facturas = base_facturas.filter(Solicitud.taller_id == taller_id)

    # Solicitudes hoy
    solicitudes_hoy = base_solicitudes.filter(
        func.date(Solicitud.created_at) == hoy
    ).count()

    # Solicitudes del mes
    solicitudes_mes = base_solicitudes.filter(
        func.date(Solicitud.created_at) >= inicio_mes
    ).count()

    # Pagos hoy
    pagos_hoy = base_facturas.filter(
        and_(
            func.date(Factura.created_at) == hoy,
            Factura.enviada == True
        )
    ).all()

    # Ingresos hoy
    ingresos_hoy = sum(f.total for f in pagos_hoy)

    # Ingresos del mes
    pagos_mes = base_facturas.filter(
        and_(
            func.date(Factura.created_at) >= inicio_mes,
            Factura.enviada == True
        )
    ).all()
    ingresos_mes = sum(f.total for f in pagos_mes)

    # Solicitudes por estado
    por_estado = {}
    for estado in EstadoSolicitud:
        count = base_solicitudes.filter(Solicitud.estado == estado).count()
        por_estado[estado.value] = count

    return {
        "fecha": hoy.isoformat(),
        "solicitudes": {
            "hoy": solicitudes_hoy,
            "mes": solicitudes_mes,
            "por_estado": por_estado,
        },
        "finanzas": {
            "ingresos_hoy": ingresos_hoy,
            "ingresos_mes": ingresos_mes,
            "total_transacciones_hoy": len(pagos_hoy),
            "total_transacciones_mes": len(pagos_mes),
        },
        "personal": {
            "total": base_personal.count(),
            "disponibles": base_personal.filter(Personal.estado == "disponible").count(),
            "ocupados": base_personal.filter(Personal.estado == "ocupado").count(),
        },
        "clientes": {
            "total": db.query(Cliente).join(Solicitud, Cliente.id == Solicitud.cliente_id).filter(
                Solicitud.taller_id == taller_id
            ).distinct().count() if taller_id else db.query(Cliente).count(),
        },
    }


@router.post("/generar")
def generar_reporte(filtros: ReporteFiltros, db: Session = Depends(get_db)):
    """Generar reporte personalizado con filtros."""
    tipo = filtros.tipo or "solicitudes"

    if tipo == "solicitudes":
        return reporte_solicitudes(filtros.fecha_inicio, filtros.fecha_fin, filtros.estado, db)
    elif tipo == "pagos":
        return reporte_pagos(filtros.fecha_inicio, filtros.fecha_fin, None, db)
    elif tipo == "personal":
        return reporte_personal(filtros.fecha_inicio, filtros.fecha_fin, db)
    elif tipo == "clientes":
        return reporte_clientes(filtros.fecha_inicio, filtros.fecha_fin, db)
    else:
        raise HTTPException(status_code=400, detail=f"Tipo de reporte no soportado: {tipo}")
