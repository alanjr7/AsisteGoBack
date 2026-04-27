from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from pydantic import BaseModel
from models import Solicitud, SolicitudCreate, SolicitudUpdate, EstadoSolicitud, AsignacionPersonalRequest
from database_sql import (
    get_db, Solicitud as SolicitudDB, Cliente, Personal, SolicitudPersonal, User,
    EstadoSolicitud as EstadoDB, TipoSolicitud as TipoDB
)
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from utils.timezone import get_now
import uuid
import json
from utils.security import decode_access_token, get_taller_id_from_token
from utils.supabase_storage import ensure_full_url

# Importar funciones WebSocket
from routers.websocket import (
    notify_solicitud_nueva,
    notify_solicitud_aceptada,
    notify_solicitud_rechazada,
    notify_estado_cambiado,
    notify_mecanico_asignado
)

router = APIRouter()


def get_current_taller_id(authorization: str = Header(None)) -> Optional[str]:
    """Extraer taller_id del token JWT."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return get_taller_id_from_token(token)


@router.get("/", response_model=List[Solicitud])
def listar_solicitudes(
    estado: Optional[EstadoSolicitud] = None,
    pendientes: bool = False,
    activas: bool = False,
    cliente_id: Optional[str] = None,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Listar solicitudes. Soporta filtrado por taller (vía token) o por cliente_id."""
    # Si se envía un token, intentar extraer taller_id
    taller_id = None
    if authorization:
        taller_id = get_current_taller_id(authorization)
    
    query = db.query(SolicitudDB).options(joinedload(SolicitudDB.cliente))

    # Prioridad de filtrado:
    # 1. Si se especifica cliente_id (usado por la app móvil)
    if cliente_id:
        query = query.filter(SolicitudDB.cliente_id == cliente_id)
    # 2. Si hay un taller_id (usado por la web admin)
    elif taller_id:
        query = query.filter(
            (SolicitudDB.taller_id == taller_id) | 
            ((SolicitudDB.taller_id.is_(None)) & (SolicitudDB.estado == EstadoDB["PENDIENTE"]))
        )
    # 3. Acceso público / sin token
    else:
        query = query.filter(SolicitudDB.taller_id.is_(None))

    if estado:
        query = query.filter(SolicitudDB.estado == estado.value)
    elif pendientes:
        query = query.filter(SolicitudDB.estado == EstadoDB["PENDIENTE"])
    elif activas:
        activos = [EstadoDB["ACEPTADA"], EstadoDB["EN_CAMINO"], EstadoDB["REPARANDO"]]
        query = query.filter(SolicitudDB.estado.in_(activos))

    return [_solicitud_to_dict(s, db) for s in query.all()]


def _convert_analisis_ia_to_camelcase(data: dict) -> dict:
    """Convertir claves de analisis_ia de snake_case a camelCase."""
    if not data:
        return None

    key_mapping = {
        'transcripcion_audio': 'transcripcionAudio',
        'tipo_problema': 'tipoProblema',
        'prioridad': 'prioridad',
        'daños_detectados': 'danosDetectados',
        'piezas_sugeridas': 'piezasSugeridas',
        'costo_estimado': 'costoEstimado',
        'tiempo_estimado_minutos': 'tiempoEstimadoMinutos',
        'resumen': 'resumen',
        'confianza': 'confianza',
    }

    return {key_mapping.get(k, k): v for k, v in data.items()}


def _parse_imagenes(imagenes_json: str) -> list:
    """Parsear campo imagenes de forma segura."""
    if not imagenes_json or imagenes_json.strip() == '':
        return []
    try:
        imagenes_list = json.loads(imagenes_json)
        if not isinstance(imagenes_list, list):
            return []
        return [ensure_full_url(img) for img in imagenes_list if img]
    except json.JSONDecodeError as e:
        print(f"[BACKEND] Error parseando imagenes: {e}")
        return []


def _parse_analisis_ia(analisis_ia_json: str) -> dict:
    """Parsear campo analisis_ia de forma segura."""
    if not analisis_ia_json or analisis_ia_json.strip() == '':
        return None
    try:
        data = json.loads(analisis_ia_json)
        if not isinstance(data, dict):
            return None
        return _convert_analisis_ia_to_camelcase(data)
    except json.JSONDecodeError as e:
        print(f"[BACKEND] Error parseando analisis_ia: {e}")
        return None


def _solicitud_to_dict(s: SolicitudDB, db: Session = None) -> dict:
    """Convertir modelo SQL a dict para respuesta API."""
    # Manejo defensivo para cliente (puede ser null o lazy load fallido)
    cliente_data = None
    try:
        if s.cliente and hasattr(s.cliente, 'id'):
            cliente_data = {
                "id": s.cliente.id,
                "nombre": s.cliente.nombre,
                "telefono": s.cliente.telefono,
                "email": s.cliente.email,
                "foto": ensure_full_url(s.cliente.foto),
                "lat": s.cliente.lat,
                "lng": s.cliente.lng,
                "veces_atendido": s.cliente.veces_atendido,
                "calificacion_promedio": s.cliente.calificacion_promedio,
            }
    except Exception as e:
        print(f"[BACKEND] Advertencia: No se pudo cargar cliente para solicitud {s.id}: {e}")
        cliente_data = None

    # Manejo defensivo para taller (puede ser null o lazy load fallido)
    taller_data = None
    try:
        if s.taller and hasattr(s.taller, 'id'):
            taller_data = {
                "id": s.taller.id,
                "nombre": s.taller.nombre,
                "lat": s.taller.lat,
                "lng": s.taller.lng,
                "direccion": s.taller.direccion,
                "telefono": s.taller.telefono,
                "calificacion": s.taller.calificacion,
            }
    except Exception as e:
        print(f"[BACKEND] Advertencia: No se pudo cargar taller para solicitud {s.id}: {e}")
        taller_data = None

    result = {
        "id": s.id,
        "cliente_id": s.cliente_id,
        "cliente": cliente_data,
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
        "estado": s.estado.value if hasattr(s.estado, 'value') else s.estado,
        "requiere_repuestos": s.requiere_repuestos,
        "tipo": s.tipo.value if hasattr(s.tipo, 'value') else s.tipo,
        "imagenes": _parse_imagenes(s.imagenes),
        "audio": ensure_full_url(s.audio) if s.audio else None,
        "mecanico_asignado": None,
        "personal_asignado": None,
        "estado_pago": s.estado_pago or "pendiente",
        "monto_pago": s.monto_pago,
        "analisisIA": _parse_analisis_ia(s.analisis_ia),
        "timestamp": s.created_at.isoformat() if s.created_at else None,
        "lat": s.lat,
        "lng": s.lng,
        "taller": taller_data,
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
                    "foto": ensure_full_url(a.personal.foto),
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
    solicitud = db.query(SolicitudDB).options(joinedload(SolicitudDB.cliente)).filter(SolicitudDB.id == solicitud_id).first()
    if not solicitud:
        print(f"[BACKEND] ERROR: Solicitud {solicitud_id} no encontrada")
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    print(f"[BACKEND] Devolviendo solicitud {solicitud_id} con estado: {solicitud.estado.value}")
    return _solicitud_to_dict(solicitud, db)


@router.post("/", response_model=Solicitud)
async def crear_solicitud(
    solicitud: SolicitudCreate,
    db: Session = Depends(get_db),
    authorization: str = Header(None),
    x_platform: str = Header("web", alias="X-Platform")
):
    """Crear nueva solicitud. Desde web asigna al taller del usuario, desde mobile puede especificar taller."""
    # Obtener taller del usuario actual (si es web)
    taller_id = get_current_taller_id(authorization)

    # Desde mobile, usar el taller_id del body si se proporciona
    if x_platform == "mobile" and solicitud.taller_id:
        taller_id = solicitud.taller_id

    # Validar cliente existe en PostgreSQL
    cliente = db.query(Cliente).filter(Cliente.id == solicitud.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Desde web requerir taller, desde mobile permitir sin asignar
    if x_platform == "web" and not taller_id:
        raise HTTPException(status_code=403, detail="Usuario no tiene un taller asignado")

    # Debug: Verificar qué análisis IA se recibe
    print(f"[BACKEND] Creando solicitud - analisis_ia recibido: {solicitud.analisis_ia}")

    # Crear solicitud en PostgreSQL
    nueva = SolicitudDB(
        id=str(uuid.uuid4()),
        cliente_id=solicitud.cliente_id,
        taller_id=taller_id,  # NULL si es mobile y no tiene taller asignado
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
        analisis_ia=json.dumps(solicitud.analisis_ia.model_dump() if solicitud.analisis_ia else None),
        lat=solicitud.lat,
        lng=solicitud.lng,
    )

    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    
    # Notificar vía WebSocket
    solicitud_dict = _solicitud_to_dict(nueva, db)
    await notify_solicitud_nueva(solicitud_dict)
    
    return solicitud_dict


@router.post("/{solicitud_id}/asignar", response_model=Solicitud)
async def asignar_solicitud_a_taller(
    solicitud_id: str,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """Asignar una solicitud sin taller al taller del usuario autenticado."""
    taller_id = get_current_taller_id(authorization)
    if not taller_id:
        raise HTTPException(status_code=403, detail="Usuario no tiene un taller asignado")
    
    # Buscar solicitud
    solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # Solo permitir asignar si está pendiente y sin taller
    if solicitud.taller_id is not None:
        raise HTTPException(status_code=400, detail="Esta solicitud ya tiene un taller asignado")
    
    if solicitud.estado != EstadoDB["PENDIENTE"]:
        raise HTTPException(status_code=400, detail="Solo se pueden asignar solicitudes pendientes")
    
    # Asignar al taller
    solicitud.taller_id = taller_id
    solicitud.estado = EstadoDB["ACEPTADA"]  # Al asignar, cambia a aceptada
    
    db.commit()
    db.refresh(solicitud)
    
    # Notificar asignación al cliente
    solicitud_dict = _solicitud_to_dict(solicitud, db)
    await notify_solicitud_aceptada(solicitud.cliente_id, solicitud_dict)
    
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

    existing.updated_at = get_now()
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
    existing.updated_at = get_now()
    
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
            asignacion.fecha_liberacion = get_now()
            # Cambiar estado del personal a disponible
            personal = db.query(Personal).filter(Personal.id == asignacion.personal_id).first()
            if personal:
                personal.estado = "disponible"
                personal.updated_at = get_now()

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
            fecha_asignacion=get_now(),
        )
        db.add(asignacion)

        # Cambiar estado del personal a ocupado
        personal.estado = "ocupado"
        personal.updated_at = get_now()

        print(f"[BACKEND] Asignado {personal.nombre} ({personal.rol}) a solicitud {solicitud_id}")

    # Cambiar estado de la solicitud a aceptada
    solicitud.estado = EstadoDB["ACEPTADA"]
    solicitud.updated_at = get_now()

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
        asignacion.fecha_liberacion = get_now()

        personal = db.query(Personal).filter(Personal.id == asignacion.personal_id).first()
        if personal:
            personal.estado = "disponible"
            personal.updated_at = get_now()
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
