from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============ ENUMS ============
class EstadoSolicitud(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    EN_CAMINO = "en_camino"
    REPARANDO = "reparando"
    FINALIZADA = "finalizada"
    RECHAZADA = "rechazada"
    CANCELADA = "cancelada"


class EstadoPago(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"


class EstadoSolicitudRepuesto(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"


class EstadoPersonal(str, Enum):
    DISPONIBLE = "disponible"
    OCUPADO = "ocupado"
    EN_CAMINO = "en_camino"
    REGRESANDO = "regresando"


class RolPersonal(str, Enum):
    MECANICO = "mecanico"
    ELECTRICO = "electrico"
    GRUA = "grua"
    ADMINISTRADOR = "administrador"
    ENCARGADO = "encargado"


class TipoSolicitud(str, Enum):
    NORMAL = "normal"
    GRUA = "grua"


class TipoNotificacion(str, Enum):
    SOLICITUD = "solicitud"
    REPUESTO = "repuesto"
    MENSAJE = "mensaje"
    PAGO = "pago"


class TipoMensaje(str, Enum):
    TEXTO = "texto"
    IMAGEN = "imagen"
    AUDIO = "audio"


class MetodoPago(str, Enum):
    QR = "qr"
    TARJETA = "tarjeta"
    EFECTIVO = "efectivo"


class EmisorMensaje(str, Enum):
    CLIENTE = "cliente"
    TALLER = "taller"


# ============ MODELOS BASE ============
class ClienteBase(BaseModel):
    nombre: str
    telefono: str
    email: Optional[str] = None
    foto: Optional[str] = None
    lat: float
    lng: float
    veces_atendido: Optional[int] = 0
    calificacion_promedio: Optional[float] = None


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    foto: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class Cliente(ClienteBase):
    id: str

    class Config:
        from_attributes = True


class VehiculoBase(BaseModel):
    marca: str
    modelo: str
    anio: int
    placa: str
    color: str
    tipo: str


class VehiculoCreate(VehiculoBase):
    pass


class Vehiculo(VehiculoBase):
    id: str

    class Config:
        from_attributes = True


class AnalisisIA(BaseModel):
    piezas_detectadas: Optional[List[str]] = None
    danos_identificados: Optional[List[str]] = None
    tipo_problema: Optional[str] = None
    recomendaciones: Optional[List[str]] = None


class SolicitudBase(BaseModel):
    descripcion: str
    distancia: float
    estado: EstadoSolicitud = EstadoSolicitud.PENDIENTE
    problema: str
    requiere_repuestos: bool
    audio: Optional[str] = None
    imagenes: Optional[List[str]] = None
    analisis_ia: Optional[AnalisisIA] = None
    tipo: TipoSolicitud = TipoSolicitud.NORMAL


class SolicitudCreate(SolicitudBase):
    cliente_id: str
    vehiculo: VehiculoCreate


class SolicitudUpdate(BaseModel):
    descripcion: Optional[str] = None
    distancia: Optional[float] = None
    estado: Optional[EstadoSolicitud] = None
    problema: Optional[str] = None
    requiere_repuestos: Optional[bool] = None
    audio: Optional[str] = None
    imagenes: Optional[List[str]] = None
    analisis_ia: Optional[AnalisisIA] = None
    tipo: Optional[TipoSolicitud] = None
    estado_pago: Optional[EstadoPago] = None
    monto_pago: Optional[float] = None


class AsignacionPersonalRequest(BaseModel):
    """Request para asignar personal a una solicitud."""
    personal_ids: List[str]  # Lista de IDs de personal a asignar


class PersonalAsignado(BaseModel):
    """Información de personal asignado a una solicitud."""
    id: str
    nombre: str
    rol: RolPersonal
    foto: Optional[str] = None
    telefono: Optional[str] = None
    fecha_asignacion: datetime

    class Config:
        from_attributes = True


class Solicitud(SolicitudBase):
    id: str
    cliente: Cliente
    vehiculo: Vehiculo
    timestamp: datetime
    mecanico_asignado: Optional["Personal"] = None
    personal_asignado: Optional[List[PersonalAsignado]] = None  # Nuevo campo para múltiples técnicos
    estado_pago: Optional[EstadoPago] = EstadoPago.PENDIENTE
    monto_pago: Optional[float] = None

    class Config:
        from_attributes = True


class ConfirmarPagoRequest(BaseModel):
    """Request para que el taller confirme el monto a cobrar."""
    solicitud_id: str
    monto: float


class ProcesarPagoRequest(BaseModel):
    """Request para que el cliente procese el pago."""
    solicitud_id: str
    metodo_pago: MetodoPago
    comprobante: Optional[str] = None


class EstadoPagoResponse(BaseModel):
    """Response con el estado de pago de una solicitud."""
    solicitud_id: str
    estado_pago: EstadoPago
    monto: Optional[float] = None
    total: Optional[float] = None  # monto + comision
    tiene_factura: bool = False
    factura_id: Optional[str] = None


class RepuestoBase(BaseModel):
    nombre: str
    descripcion: str
    precio: float
    imagen: Optional[str] = None
    disponible: bool = True
    marca: str
    categoria: str
    vehiculos_compatibles: List[str]


class RepuestoCreate(RepuestoBase):
    pass


class RepuestoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    imagen: Optional[str] = None
    disponible: Optional[bool] = None
    marca: Optional[str] = None
    categoria: Optional[str] = None
    vehiculos_compatibles: Optional[List[str]] = None


class Repuesto(RepuestoBase):
    id: str

    class Config:
        from_attributes = True


class SolicitudRepuestoBase(BaseModel):
    repuesto_id: str
    cliente_id: str
    vehiculo: VehiculoCreate
    cantidad: int = 1
    estado: EstadoSolicitudRepuesto = EstadoSolicitudRepuesto.PENDIENTE
    imagen_referencia: Optional[str] = None


class SolicitudRepuestoCreate(SolicitudRepuestoBase):
    pass


class SolicitudRepuestoUpdate(BaseModel):
    cantidad: Optional[int] = None
    estado: Optional[EstadoSolicitudRepuesto] = None
    imagen_referencia: Optional[str] = None


class SolicitudRepuesto(SolicitudRepuestoBase):
    id: str
    timestamp: datetime
    repuesto: Optional[Repuesto] = None
    cliente: Optional[Cliente] = None

    class Config:
        from_attributes = True


class ServicioBase(BaseModel):
    solicitud_id: str
    problema: str
    solucion: str
    monto: float
    duracion: int


class ServicioCreate(ServicioBase):
    cliente_id: str
    vehiculo: VehiculoCreate


class ServicioUpdate(BaseModel):
    problema: Optional[str] = None
    solucion: Optional[str] = None
    monto: Optional[float] = None
    duracion: Optional[int] = None


class Servicio(ServicioBase):
    id: str
    cliente: Cliente
    vehiculo: Vehiculo
    fecha: datetime

    class Config:
        from_attributes = True


class NotificacionBase(BaseModel):
    tipo: TipoNotificacion
    titulo: str
    mensaje: str
    leida: bool = False


class NotificacionCreate(NotificacionBase):
    pass


class NotificacionUpdate(BaseModel):
    leida: Optional[bool] = None


class Notificacion(NotificacionBase):
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True


class MensajeChatBase(BaseModel):
    emisor: EmisorMensaje
    contenido: str
    tipo: TipoMensaje = TipoMensaje.TEXTO
    imagen: Optional[str] = None
    audio: Optional[str] = None
    transcripcion: Optional[str] = None


class MensajeChatCreate(MensajeChatBase):
    solicitud_id: str


class MensajeChat(MensajeChatBase):
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True


class PersonalBase(BaseModel):
    nombre: str
    rol: RolPersonal
    estado: Optional[EstadoPersonal] = None
    foto: Optional[str] = None
    telefono: Optional[str] = None
    asistencias_dia: int = 0
    asistencias_mes: int = 0


class PersonalCreate(PersonalBase):
    pass


class PersonalUpdate(BaseModel):
    nombre: Optional[str] = None
    rol: Optional[RolPersonal] = None
    estado: Optional[EstadoPersonal] = None
    foto: Optional[str] = None
    telefono: Optional[str] = None
    asistencias_dia: Optional[int] = None
    asistencias_mes: Optional[int] = None


class Personal(PersonalBase):
    id: str

    class Config:
        from_attributes = True


class FacturaBase(BaseModel):
    solicitud_id: str
    cliente_id: str
    monto: float
    comision: float
    total: float
    metodo_pago: MetodoPago
    comprobante: Optional[str] = None
    enviada: bool = False


class FacturaCreate(FacturaBase):
    pass


class FacturaUpdate(BaseModel):
    monto: Optional[float] = None
    comision: Optional[float] = None
    total: Optional[float] = None
    metodo_pago: Optional[MetodoPago] = None
    comprobante: Optional[str] = None
    enviada: Optional[bool] = None


class Factura(FacturaBase):
    id: str
    fecha: datetime
    cliente: Optional[Cliente] = None

    class Config:
        from_attributes = True


class TallerBase(BaseModel):
    nombre: str
    foto: Optional[str] = None
    ubicacion: str
    telefono: str
    email: str
    calificacion: float = 0.0
    total_servicios: int = 0
    descripcion: Optional[str] = None


class TallerCreate(TallerBase):
    pass


class TallerUpdate(BaseModel):
    nombre: Optional[str] = None
    foto: Optional[str] = None
    ubicacion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    calificacion: Optional[float] = None
    total_servicios: Optional[int] = None
    descripcion: Optional[str] = None


class Taller(TallerBase):
    id: str

    class Config:
        from_attributes = True


class CalificacionBase(BaseModel):
    servicio_id: str
    cliente_id: str
    estrellas: int = Field(..., ge=1, le=5)
    comentarios: List[str] = []


class CalificacionCreate(CalificacionBase):
    pass


class Calificacion(CalificacionBase):
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = False


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str


class RegisterRequest(BaseModel):
    nombre: str
    email: str
    password: str


class RegisterResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str
    user: Optional[dict] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str


class StatsResponse(BaseModel):
    total_servicios: int
    servicios_hoy: int
    servicios_mes: int
    ingresos_totales: float
    calificacion_promedio: float


# ============ EVIDENCIAS ============
class TipoEvidencia(str, Enum):
    IMAGEN = "imagen"
    AUDIO = "audio"
    VIDEO = "video"


class EvidenciaBase(BaseModel):
    solicitud_id: str
    tipo: TipoEvidencia
    url: str
    descripcion: Optional[str] = None
    subido_por: str  # ID del usuario (cliente o mecanico)
    lat: Optional[float] = None
    lng: Optional[float] = None


class EvidenciaCreate(EvidenciaBase):
    pass


class Evidencia(EvidenciaBase):
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ============ COMPROBANTES DE PAGO ============
class ComprobantePagoBase(BaseModel):
    solicitud_id: str
    monto: float
    metodo_pago: MetodoPago
    url_imagen: Optional[str] = None  # URL del comprobante subido
    notas: Optional[str] = None
    verificado: bool = False


class ComprobantePagoCreate(ComprobantePagoBase):
    pass


class ComprobantePago(ComprobantePagoBase):
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ============ UBICACIÓN GRÚA ============
class UbicacionGruaBase(BaseModel):
    gruista_id: str
    lat: float
    lng: float
    disponible: bool = True
    en_servicio: bool = False
    solicitud_id: Optional[str] = None  # Si está en servicio, a qué solicitud


class UbicacionGruaUpdate(BaseModel):
    lat: float
    lng: float
    disponible: Optional[bool] = None
    en_servicio: Optional[bool] = None
    solicitud_id: Optional[str] = None


class UbicacionGrua(UbicacionGruaBase):
    id: str
    timestamp: datetime

    class Config:
        from_attributes = True


class AsignacionGruaRequest(BaseModel):
    solicitud_id: str
    lat_cliente: float
    lng_cliente: float


class AsignacionGruaResponse(BaseModel):
    success: bool
    message: str
    gruista_id: Optional[str] = None
    gruista_nombre: Optional[str] = None
    distancia_km: Optional[float] = None
    tiempo_estimado_min: Optional[int] = None
