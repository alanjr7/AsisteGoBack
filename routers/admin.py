"""Router para administración global del sistema (solo administradores)."""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from database_sql import get_db, User, Taller, Cliente, Solicitud, Personal, Factura, Repuesto, EstadoSolicitud
from utils.security import decode_access_token
from models import Taller as TallerModel, Cliente as ClienteModel

router = APIRouter(prefix="/admin", tags=["Administración"])


def get_current_admin(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Verificar que el usuario actual es administrador."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    if user.rol != "administrador":
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder a este recurso")

    return user


@router.get("/stats")
def estadisticas_globales(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Obtener estadísticas globales del sistema."""
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)

    # Conteos globales
    total_talleres = db.query(Taller).count()
    total_clientes = db.query(Cliente).count()
    total_solicitudes = db.query(Solicitud).count()
    total_personal = db.query(Personal).count()
    total_repuestos = db.query(Repuesto).count()

    # Solicitudes por estado
    solicitudes_por_estado = {}
    for estado in EstadoSolicitud:
        count = db.query(Solicitud).filter(Solicitud.estado == estado).count()
        solicitudes_por_estado[estado.value] = count

    # Finanzas
    facturas = db.query(Factura).all()
    ingresos_totales = sum(f.total for f in facturas)
    comisiones_totales = sum(f.comision for f in facturas)

    # Solicitudes hoy y mes
    solicitudes_hoy = db.query(Solicitud).filter(
        func.date(Solicitud.created_at) == hoy
    ).count()

    solicitudes_mes = db.query(Solicitud).filter(
        func.date(Solicitud.created_at) >= inicio_mes
    ).count()

    # Usuarios registrados hoy
    usuarios_hoy = db.query(User).filter(
        func.date(User.created_at) == hoy
    ).count()

    return {
        "fecha_actual": hoy.isoformat(),
        "conteos": {
            "talleres": total_talleres,
            "clientes": total_clientes,
            "solicitudes": total_solicitudes,
            "personal": total_personal,
            "repuestos": total_repuestos,
            "usuarios_registrados": db.query(User).count()
        },
        "solicitudes": {
            "por_estado": solicitudes_por_estado,
            "hoy": solicitudes_hoy,
            "mes": solicitudes_mes
        },
        "finanzas": {
            "ingresos_totales": ingresos_totales,
            "comisiones_totales": comisiones_totales,
            "monto_neto": ingresos_totales - comisiones_totales
        },
        "actividad_hoy": {
            "nuevas_solicitudes": solicitudes_hoy,
            "nuevos_usuarios": usuarios_hoy
        }
    }


@router.get("/talleres", response_model=List[TallerModel])
def listar_todos_talleres(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Listar todos los talleres del sistema."""
    talleres = db.query(Taller).all()
    return talleres


@router.get("/clientes")
def listar_todos_clientes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Listar todos los clientes con paginación."""
    clientes = db.query(Cliente).offset(skip).limit(limit).all()
    total = db.query(Cliente).count()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "clientes": clientes
    }


@router.get("/solicitudes")
def listar_todas_solicitudes(
    skip: int = 0,
    limit: int = 100,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Listar todas las solicitudes del sistema con filtros opcionales."""
    query = db.query(Solicitud)

    if estado:
        try:
            estado_enum = EstadoSolicitud(estado)
            query = query.filter(Solicitud.estado == estado_enum)
        except ValueError:
            pass

    total = query.count()
    solicitudes = query.order_by(Solicitud.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "solicitudes": solicitudes
    }


@router.get("/finanzas")
def reporte_financiero_global(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Reporte financiero global del sistema."""
    if not fecha_inicio or not fecha_fin:
        fecha_fin = date.today()
        fecha_inicio = fecha_fin - timedelta(days=30)

    facturas = db.query(Factura).filter(
        and_(
            func.date(Factura.created_at) >= fecha_inicio,
            func.date(Factura.created_at) <= fecha_fin
        )
    ).all()

    # Agrupar por método de pago
    por_metodo = {}
    for f in facturas:
        met = f.metodo_pago or "desconocido"
        por_metodo[met] = por_metodo.get(met, 0) + 1

    # Ingresos por día
    ingresos_por_dia = {}
    for f in facturas:
        dia = f.created_at.strftime("%Y-%m-%d")
        if dia not in ingresos_por_dia:
            ingresos_por_dia[dia] = 0
        ingresos_por_dia[dia] += f.total

    return {
        "periodo": {
            "inicio": fecha_inicio.isoformat(),
            "fin": fecha_fin.isoformat()
        },
        "resumen": {
            "total_facturas": len(facturas),
            "monto_total": sum(f.total for f in facturas),
            "comisiones_total": sum(f.comision for f in facturas),
            "promedio_factura": sum(f.total for f in facturas) / len(facturas) if facturas else 0
        },
        "por_metodo_pago": por_metodo,
        "ingresos_por_dia": ingresos_por_dia
    }


@router.get("/actividad-reciente")
def actividad_reciente(
    limit: int = 20,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Obtener actividad reciente del sistema."""
    # Solicitudes recientes
    solicitudes_recientes = db.query(Solicitud).order_by(
        Solicitud.created_at.desc()
    ).limit(limit).all()

    # Nuevos usuarios recientes
    usuarios_recientes = db.query(User).order_by(
        User.created_at.desc()
    ).limit(limit).all()

    return {
        "solicitudes_recientes": [
            {
                "id": s.id,
                "estado": s.estado.value if hasattr(s.estado, 'value') else str(s.estado),
                "problema": s.problema,
                "timestamp": s.created_at.isoformat() if s.created_at else None
            }
            for s in solicitudes_recientes
        ],
        "usuarios_recientes": [
            {
                "id": u.id,
                "nombre": u.nombre,
                "email": u.email,
                "rol": u.rol,
                "tipo_usuario": u.tipo_usuario,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in usuarios_recientes
        ]
    }


@router.get("/usuarios")
def listar_usuarios(
    skip: int = 0,
    limit: int = 100,
    rol: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Listar todos los usuarios del sistema."""
    query = db.query(User)

    if rol:
        query = query.filter(User.rol == rol)

    total = query.count()
    usuarios = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "usuarios": [
            {
                "id": u.id,
                "nombre": u.nombre,
                "email": u.email,
                "rol": u.rol,
                "tipo_usuario": u.tipo_usuario,
                "taller_id": u.taller_id,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "bloqueado_hasta": u.bloqueado_hasta.isoformat() if u.bloqueado_hasta else None
            }
            for u in usuarios
        ]
    }
