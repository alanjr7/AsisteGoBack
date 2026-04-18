from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from models import Solicitud, SolicitudCreate, SolicitudUpdate, EstadoSolicitud, AsignacionPersonalRequest
from database_sql import (
    get_db, Solicitud as SolicitudDB, Cliente, Personal, SolicitudPersonal,
    EstadoSolicitud as EstadoDB, TipoSolicitud as TipoDB
)
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import json

# Importar funciones WebSocket
from routers.websocket import (
    notify_solicitud_nueva,
    notify_solicitud_aceptada,
    notify_solicitud_rechazada,
    notify_estado_cambiado,
    notify_mecanico_asignado
)

router = APIRouter()


@router.get("/", response_model=List[Solicitud])
def listar_solicitudes(
    estado: Optional[EstadoSolicitud] = None,
    pendientes: bool = False,
    activas: bool = False,
    db: Session = Depends(get_db)
):
    """Listar solicitudes con filtros opcionales."""
    query = db.query(SolicitudDB)

    if estado:
        query = query.filter(SolicitudDB.estado == estado.value)
    elif pendientes:
        query = query.filter(SolicitudDB.estado == EstadoDB["PENDIENTE"])
    elif activas:
        activos = [EstadoDB["ACEPTADA"], EstadoDB["EN_CAMINO"], EstadoDB["REPARANDO"]]
        query = query.filter(SolicitudDB.estado.in_(activos))

    return [_solicitud_to_dict(s, db) for s in query.all()]


def _solicitud_to_dict(s: SolicitudDB, db: Session = None) -> dict:
    """Convertir modelo SQL a dict para respuesta API."""
    result = {
        "id": s.id,
        "cliente_id": s.cliente_id,
        "cliente": {
            "id": s.cliente.id,
            "nombre": s.cliente.nombre,
            "telefono": s.cliente.telefono,
            "email": s.cliente.email,
            "foto": s.cliente.foto,
            "lat": s.cliente.lat,
            "lng": s.cliente.lng,
            "veces_atendido": s.cliente.veces_atendido,
            "calificacion_promedio": s.cliente.calificacion_promedio,
        } if s.cliente else None,
        "vehiculo": {
            "id": str(uuid.uuid4()),
            "marca": s.vehiculo_marca,
            "modelo": s.vehiculo_modelo,
            "anio": s.vehiculo_anio,
            "placa": s.vehiculo_placa,
            "color": s.vehiculo_color,
            "tipo": s.vehiculo_tipo,
        },
        "descripcion": s.descripcion,
        "problema": s.problema,
        "distancia": s.distancia,
        "estado": s.estado.value,
        "requiere_repuestos": s.requiere_repuestos,
        "tipo": s.tipo.value,
        "imagenes": json.loads(s.imagenes) if s.imagenes else [],
        "audio": s.audio,
        "mecanico_asignado": None,
        "personal_asignado": None,
        "estado_pago": s.estado_pago or "pendiente",
        "monto_pago": s.monto_pago,
        "timestamp": s.created_at.isoformat() if s.created_at else None,
    }

    # Cargar personal asignado si hay conexión a DB
    if db:
        asignaciones = db.query(SolicitudPersonal).filter(
            SolicitudPersonal.solicitud_id == s.id,
            SolicitudPersonal.fecha_liberacion.is_(None)
        ).all()

        if asignaciones:
            result["personal_asignado"] = [
                {
                    "id": a.personal.id,
                    "nombre": a.personal.nombre,
                    "rol": a.personal.rol,
                    "foto": a.personal.foto,
                    "telefono": a.personal.telefono,
                    "fecha_asignacion": a.fecha_asignacion.isoformat() if a.fecha_asignacion else None,
                }
                for a in asignaciones if a.personal
            ]

    return result


@router.get("/{solicitud_id}", response_model=Solicitud)
def obtener_solicitud(solicitud_id: str, db: Session = Depends(get_db)):
    """Obtener solicitud por ID."""
    print(f"[BACKEND] GET solicitud {solicitud_id}")
    solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not solicitud:
        print(f"[BACKEND] ERROR: Solicitud {solicitud_id} no encontrada")
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    print(f"[BACKEND] Devolviendo solicitud {solicitud_id} con estado: {solicitud.estado.value}")
    return _solicitud_to_dict(solicitud, db)


@router.post("/", response_model=Solicitud)
async def crear_solicitud(solicitud: SolicitudCreate, db: Session = Depends(get_db)):
    """Crear nueva solicitud."""
    # Validar cliente existe en MySQL
    cliente = db.query(Cliente).filter(Cliente.id == solicitud.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Crear solicitud en MySQL
    nueva = SolicitudDB(
        id=str(uuid.uuid4()),
        cliente_id=solicitud.cliente_id,
        vehiculo_marca=solicitud.vehiculo.marca,
        vehiculo_modelo=solicitud.vehiculo.modelo,
        vehiculo_anio=solicitud.vehiculo.anio,
        vehiculo_placa=solicitud.vehiculo.placa,
        vehiculo_color=solicitud.vehiculo.color,
        vehiculo_tipo=solicitud.vehiculo.tipo,
        descripcion=solicitud.descripcion,
        problema=solicitud.problema,
        distancia=solicitud.distancia,
        estado=EstadoDB["PENDIENTE"],
        requiere_repuestos=solicitud.requiere_repuestos,
        tipo=TipoDB(solicitud.tipo.value) if hasattr(solicitud.tipo, 'value') else TipoDB.NORMAL,
        imagenes=json.dumps(solicitud.imagenes or []),
        audio=solicitud.audio,
    )

    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    
    # Notificar al taller vía WebSocket
    solicitud_dict = _solicitud_to_dict(nueva, db)
    await notify_solicitud_nueva(solicitud_dict)
    
    return solicitud_dict


@router.put("/{solicitud_id}", response_model=Solicitud)
def actualizar_solicitud(solicitud_id: str, solicitud: SolicitudUpdate, db: Session = Depends(get_db)):
    """Actualizar solicitud."""
    existing = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    data = solicitud.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "estado" and value:
            value = EstadoDB(value.value) if hasattr(value, 'value') else EstadoDB(value)
        elif key == "imagenes" and value is not None:
            value = json.dumps(value)
        if hasattr(existing, key):
            setattr(existing, key, value)

    existing.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(existing)
    return _solicitud_to_dict(existing, db)


class EstadoUpdate(BaseModel):
    estado: EstadoSolicitud

@router.put("/{solicitud_id}/estado")
async def cambiar_estado(solicitud_id: str, data: EstadoUpdate, db: Session = Depends(get_db)):
    """Cambiar estado de la solicitud."""
    print(f"[BACKEND] Cambiando estado de solicitud {solicitud_id} a: {data.estado.value}")

    existing = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not existing:
        print(f"[BACKEND] ERROR: Solicitud {solicitud_id} no encontrada")
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    estado_anterior = existing.estado.value
    existing.estado = EstadoDB[data.estado.name]
    existing.updated_at = datetime.utcnow()
    
    # Guardar referencia al cliente_id para notificaciones
    cliente_id = existing.cliente_id

    # Si la solicitud se finaliza, liberar el personal asignado
    if data.estado.value == "finalizada":
        print(f"[BACKEND] Liberando personal de solicitud {solicitud_id}")
        asignaciones = db.query(SolicitudPersonal).filter(
            SolicitudPersonal.solicitud_id == solicitud_id,
            SolicitudPersonal.fecha_liberacion.is_(None)
        ).all()

        for asignacion in asignaciones:
            asignacion.fecha_liberacion = datetime.utcnow()
            # Cambiar estado del personal a disponible
            personal = db.query(Personal).filter(Personal.id == asignacion.personal_id).first()
            if personal:
                personal.estado = "disponible"
                personal.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(existing)
    
    resultado = _solicitud_to_dict(existing, db)

    # Notificar cambio de estado vía WebSocket
    if data.estado.value == "aceptada":
        await notify_solicitud_aceptada(cliente_id, resultado)
    elif data.estado.value == "rechazada":
        await notify_solicitud_rechazada(cliente_id, solicitud_id)
    elif data.estado.value == "finalizada":
        # Notificar al cliente que puede pagar
        from routers.websocket import notify_servicio_finalizado
        await notify_servicio_finalizado(cliente_id, resultado)
    
    # Siempre notificar el cambio de estado a la room de la solicitud
    await notify_estado_cambiado(solicitud_id, data.estado.value, resultado)

    print(f"[BACKEND] Estado cambiado exitosamente: {estado_anterior} -> {data.estado.value}")
    return resultado


@router.put("/{solicitud_id}/asignar")
async def asignar_personal(
    solicitud_id: str,
    request: AsignacionPersonalRequest,
    db: Session = Depends(get_db)
):
    """Asignar personal (uno o varios) a la solicitud y aceptarla."""
    print(f"[BACKEND] Asignando personal a solicitud {solicitud_id}: {request.personal_ids}")

    solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if not request.personal_ids:
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos un ID de personal")

    # Validar que todo el personal existe y está disponible
    for personal_id in request.personal_ids:
        personal = db.query(Personal).filter(Personal.id == personal_id).first()
        if not personal:
            raise HTTPException(status_code=404, detail=f"Personal con ID {personal_id} no encontrado")
        if personal.estado != "disponible":
            raise HTTPException(
                status_code=400,
                detail=f"El personal {personal.nombre} no está disponible (estado: {personal.estado})"
            )

    # Crear asignaciones en tabla intermedia y marcar personal como ocupado
    for personal_id in request.personal_ids:
        personal = db.query(Personal).filter(Personal.id == personal_id).first()

        # Crear registro de asignación
        asignacion = SolicitudPersonal(
            id=str(uuid.uuid4()),
            solicitud_id=solicitud_id,
            personal_id=personal_id,
            rol_asignado=personal.rol,
            fecha_asignacion=datetime.utcnow(),
        )
        db.add(asignacion)

        # Cambiar estado del personal a ocupado
        personal.estado = "ocupado"
        personal.updated_at = datetime.utcnow()

        print(f"[BACKEND] Asignado {personal.nombre} ({personal.rol}) a solicitud {solicitud_id}")

    # Cambiar estado de la solicitud a aceptada
    solicitud.estado = EstadoDB["ACEPTADA"]
    solicitud.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(solicitud)
    
    resultado = _solicitud_to_dict(solicitud, db)

    # Notificar al cliente vía WebSocket que la solicitud fue aceptada
    await notify_solicitud_aceptada(solicitud.cliente_id, resultado)
    
    # Notificar mecánico asignado
    for personal_id in request.personal_ids:
        personal = db.query(Personal).filter(Personal.id == personal_id).first()
        if personal:
            await notify_mecanico_asignado(solicitud.cliente_id, {
                "id": personal.id,
                "nombre": personal.nombre,
                "rol": personal.rol
            }, solicitud_id)

    print(f"[BACKEND] Solicitud {solicitud_id} aceptada con {len(request.personal_ids)} asignaciones")
    return resultado


@router.post("/{solicitud_id}/liberar")
def liberar_personal(solicitud_id: str, db: Session = Depends(get_db)):
    """Liberar todo el personal asignado a una solicitud."""
    print(f"[BACKEND] Liberando personal de solicitud {solicitud_id}")

    solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Obtener asignaciones activas
    asignaciones = db.query(SolicitudPersonal).filter(
        SolicitudPersonal.solicitud_id == solicitud_id,
        SolicitudPersonal.fecha_liberacion.is_(None)
    ).all()

    if not asignaciones:
        return {"success": True, "message": "No hay personal asignado a esta solicitud"}

    # Liberar cada asignación y marcar personal como disponible
    for asignacion in asignaciones:
        asignacion.fecha_liberacion = datetime.utcnow()

        personal = db.query(Personal).filter(Personal.id == asignacion.personal_id).first()
        if personal:
            personal.estado = "disponible"
            personal.updated_at = datetime.utcnow()
            print(f"[BACKEND] Personal {personal.nombre} liberado")

    db.commit()

    return {"success": True, "message": f"{len(asignaciones)} empleados liberados"}


@router.delete("/{solicitud_id}")
def cancelar_solicitud(solicitud_id: str, db: Session = Depends(get_db)):
    """Cancelar/eliminar solicitud."""
    existing = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    db.delete(existing)
    db.commit()
    return {"success": True, "message": "Solicitud cancelada"}
