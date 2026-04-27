"""Router para evaluación de incidentes y diagnósticos."""
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional, List
from datetime import datetime
from utils.timezone import get_now
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from database_sql import get_db, Solicitud as SolicitudDB, Cliente, Personal
from utils.openrouter_client import get_openrouter_client
from utils.rate_limiter import limiter, IA_BURST_LIMIT

router = APIRouter()


class EvaluacionBase(BaseModel):
    """Modelo base para evaluación de incidente."""
    solicitud_id: str
    diagnostico: str
    gravedad: str  # baja, media, alta, critica
    tiempo_estimado_reparacion: int  # minutos
    costo_estimado: float
    repuestos_necesarios: Optional[List[str]] = []
    requiere_grua: bool = False
    notas_internas: Optional[str] = None


class EvaluacionCreate(EvaluacionBase):
    """Modelo para crear evaluación."""
    evaluador_id: str  # ID del personal que evalúa


class EvaluacionUpdate(BaseModel):
    """Modelo para actualizar evaluación."""
    diagnostico: Optional[str] = None
    gravedad: Optional[str] = None
    tiempo_estimado_reparacion: Optional[int] = None
    costo_estimado: Optional[float] = None
    repuestos_necesarios: Optional[List[str]] = None
    requiere_grua: Optional[bool] = None
    notas_internas: Optional[str] = None


class Evaluacion(EvaluacionBase):
    """Modelo completo de evaluación."""
    id: str
    evaluador_id: str
    evaluador_nombre: Optional[str] = None
    fecha_evaluacion: datetime
    estado: str  # pendiente, aprobada, rechazada

    class Config:
        from_attributes = True


class EvaluacionDB:
    """Almacenamiento en memoria temporal para evaluaciones.
    En producción se migraría a SQL."""
    def __init__(self):
        self.evaluaciones = {}

    def create(self, data: dict) -> dict:
        eval_id = str(uuid.uuid4())
        evaluacion = {
            "id": eval_id,
            **data,
            "fecha_evaluacion": get_now().isoformat(),
            "estado": "pendiente"
        }
        self.evaluaciones[eval_id] = evaluacion
        return evaluacion

    def get(self, eval_id: str) -> Optional[dict]:
        return self.evaluaciones.get(eval_id)

    def get_by_solicitud(self, solicitud_id: str) -> Optional[dict]:
        for ev in self.evaluaciones.values():
            if ev.get("solicitud_id") == solicitud_id:
                return ev
        return None

    def list_all(self) -> List[dict]:
        return list(self.evaluaciones.values())

    def update(self, eval_id: str, data: dict) -> Optional[dict]:
        if eval_id not in self.evaluaciones:
            return None
        self.evaluaciones[eval_id].update(data)
        return self.evaluaciones[eval_id]

    def delete(self, eval_id: str) -> bool:
        if eval_id in self.evaluaciones:
            del self.evaluaciones[eval_id]
            return True
        return False

    def cambiar_estado(self, eval_id: str, estado: str) -> Optional[dict]:
        if eval_id not in self.evaluaciones:
            return None
        self.evaluaciones[eval_id]["estado"] = estado
        return self.evaluaciones[eval_id]


# Instancia global del storage de evaluaciones
evaluaciones_storage = EvaluacionDB()


@router.get("/", response_model=List[Evaluacion])
def listar_evaluaciones(
    solicitud_id: Optional[str] = None,
    gravedad: Optional[str] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Listar todas las evaluaciones con filtros opcionales."""
    evaluaciones = evaluaciones_storage.list_all()

    if solicitud_id:
        evaluaciones = [e for e in evaluaciones if e.get("solicitud_id") == solicitud_id]

    if gravedad:
        evaluaciones = [e for e in evaluaciones if e.get("gravedad") == gravedad]

    if estado:
        evaluaciones = [e for e in evaluaciones if e.get("estado") == estado]

    # Enriquecer con nombre del evaluador
    for ev in evaluaciones:
        evaluador = db.query(Personal).filter(Personal.id == ev.get("evaluador_id")).first()
        ev["evaluador_nombre"] = evaluador.nombre if evaluador else "Desconocido"

    return evaluaciones


@router.get("/{evaluacion_id}", response_model=Evaluacion)
def obtener_evaluacion(evaluacion_id: str, db: Session = Depends(get_db)):
    """Obtener evaluación por ID."""
    evaluacion = evaluaciones_storage.get(evaluacion_id)
    if not evaluacion:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    # Enriquecer con nombre del evaluador
    evaluador = db.query(Personal).filter(Personal.id == evaluacion.get("evaluador_id")).first()
    evaluacion["evaluador_nombre"] = evaluador.nombre if evaluador else "Desconocido"

    return evaluacion


@router.get("/solicitud/{solicitud_id}", response_model=Optional[Evaluacion])
def obtener_evaluacion_por_solicitud(solicitud_id: str, db: Session = Depends(get_db)):
    """Obtener evaluación asociada a una solicitud."""
    evaluacion = evaluaciones_storage.get_by_solicitud(solicitud_id)
    if not evaluacion:
        return None

    # Enriquecer con nombre del evaluador
    evaluador = db.query(Personal).filter(Personal.id == evaluacion.get("evaluador_id")).first()
    evaluacion["evaluador_nombre"] = evaluador.nombre if evaluador else "Desconocido"

    return evaluacion


@router.post("/", response_model=Evaluacion)
def crear_evaluacion(data: EvaluacionCreate, db: Session = Depends(get_db)):
    """Crear nueva evaluación de incidente."""
    # Verificar que la solicitud existe
    solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == data.solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Verificar que el evaluador existe
    evaluador = db.query(Personal).filter(Personal.id == data.evaluador_id).first()
    if not evaluador:
        raise HTTPException(status_code=404, detail="Evaluador no encontrado")

    # Verificar que no exista evaluación previa para esta solicitud
    existing = evaluaciones_storage.get_by_solicitud(data.solicitud_id)
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una evaluación para esta solicitud")

    # Crear evaluación
    evaluacion = evaluaciones_storage.create(data.model_dump())
    evaluacion["evaluador_nombre"] = evaluador.nombre

    return evaluacion


@router.put("/{evaluacion_id}", response_model=Evaluacion)
def actualizar_evaluacion(
    evaluacion_id: str,
    data: EvaluacionUpdate,
    db: Session = Depends(get_db)
):
    """Actualizar evaluación existente."""
    evaluacion = evaluaciones_storage.get(evaluacion_id)
    if not evaluacion:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    # No permitir modificar evaluaciones aprobadas o rechazadas
    if evaluacion.get("estado") in ["aprobada", "rechazada"]:
        raise HTTPException(status_code=400, detail="No se puede modificar una evaluación ya procesada")

    update_data = data.model_dump(exclude_unset=True)
    updated = evaluaciones_storage.update(evaluacion_id, update_data)

    # Enriquecer con nombre del evaluador
    evaluador = db.query(Personal).filter(Personal.id == updated.get("evaluador_id")).first()
    updated["evaluador_nombre"] = evaluador.nombre if evaluador else "Desconocido"

    return updated


@router.put("/{evaluacion_id}/aprobar")
def aprobar_evaluacion(evaluacion_id: str, db: Session = Depends(get_db)):
    """Aprobar evaluación y proceder con el servicio."""
    evaluacion = evaluaciones_storage.get(evaluacion_id)
    if not evaluacion:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    if evaluacion.get("estado") != "pendiente":
        raise HTTPException(status_code=400, detail="La evaluación ya fue procesada")

    updated = evaluaciones_storage.cambiar_estado(evaluacion_id, "aprobada")

    # Opcional: actualizar la solicitud con información de la evaluación
    solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == evaluacion["solicitud_id"]).first()
    if solicitud:
        # Marcar que requiere repuestos si la evaluación lo indica
        if evaluacion.get("repuestos_necesarios"):
            solicitud.requiere_repuestos = True
        db.commit()

    return {"success": True, "message": "Evaluación aprobada", "evaluacion": updated}


@router.put("/{evaluacion_id}/rechazar")
def rechazar_evaluacion(evaluacion_id: str, motivo: Optional[str] = None, db: Session = Depends(get_db)):
    """Rechazar evaluación."""
    evaluacion = evaluaciones_storage.get(evaluacion_id)
    if not evaluacion:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    if evaluacion.get("estado") != "pendiente":
        raise HTTPException(status_code=400, detail="La evaluación ya fue procesada")

    updated = evaluaciones_storage.cambiar_estado(evaluacion_id, "rechazada")
    if motivo:
        updated["motivo_rechazo"] = motivo

    return {"success": True, "message": "Evaluación rechazada", "evaluacion": updated}


@router.delete("/{evaluacion_id}")
def eliminar_evaluacion(evaluacion_id: str):
    """Eliminar evaluación (solo si está pendiente)."""
    evaluacion = evaluaciones_storage.get(evaluacion_id)
    if not evaluacion:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    if evaluacion.get("estado") != "pendiente":
        raise HTTPException(status_code=400, detail="No se puede eliminar una evaluación procesada")

    evaluaciones_storage.delete(evaluacion_id)
    return {"success": True, "message": "Evaluación eliminada"}


@router.get("/stats/resumen")
def estadisticas_evaluaciones():
    """Obtener estadísticas de evaluaciones."""
    evaluaciones = evaluaciones_storage.list_all()

    por_gravedad = {}
    por_estado = {}
    costo_total = 0
    tiempo_total = 0
    requieren_grua = 0
    con_repuestos = 0

    for ev in evaluaciones:
        gravedad = ev.get("gravedad", "desconocida")
        por_gravedad[gravedad] = por_gravedad.get(gravedad, 0) + 1

        estado = ev.get("estado", "desconocido")
        por_estado[estado] = por_estado.get(estado, 0) + 1

        costo_total += ev.get("costo_estimado", 0)
        tiempo_total += ev.get("tiempo_estimado_reparacion", 0)

        if ev.get("requiere_grua"):
            requieren_grua += 1

        if ev.get("repuestos_necesarios"):
            con_repuestos += 1

    return {
        "total_evaluaciones": len(evaluaciones),
        "por_gravedad": por_gravedad,
        "por_estado": por_estado,
        "promedio_costo": costo_total / len(evaluaciones) if evaluaciones else 0,
        "promedio_tiempo": tiempo_total / len(evaluaciones) if evaluaciones else 0,
        "requieren_grua": requieren_grua,
        "con_repuestos": con_repuestos,
    }


class DiagnosticoIAResponse(BaseModel):
    """Respuesta del diagnóstico por IA."""
    diagnostico: dict
    modelo_usado: str
    tokens_usados: int
    solicitud_id: str


@router.post("/solicitud/{solicitud_id}/diagnostico-ia", response_model=DiagnosticoIAResponse)
@limiter.limit(IA_BURST_LIMIT)
def generar_diagnostico_ia(
    request: Request,
    solicitud_id: str,
    db: Session = Depends(get_db)
):
    """
    Generar diagnóstico automático usando IA basado en la descripción de la solicitud.
    Solo analiza el texto de la descripción, no procesa imágenes ni audio.
    Rate limit: 5 requests por minuto por IP (operación más costosa).
    """
    try:
        # Obtener solicitud
        solicitud = db.query(SolicitudDB).filter(SolicitudDB.id == solicitud_id).first()
        if not solicitud:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada")

        # Verificar que tenga descripción
        if not solicitud.descripcion:
            raise HTTPException(
                status_code=400,
                detail="La solicitud no tiene descripción del problema"
            )

        # Construir info del vehículo
        vehiculo_info = {
            "marca": solicitud.vehiculo_marca,
            "modelo": solicitud.vehiculo_modelo,
            "anio": solicitud.vehiculo_anio,
            "tipo": solicitud.vehiculo_tipo,
        }

        # Llamar a OpenRouter para diagnóstico
        client = get_openrouter_client()
        resultado = client.generar_diagnostico(solicitud.descripcion, vehiculo_info)

        if resultado["success"]:
            diagnostico_data = resultado["diagnostico"]

            # Crear evaluación automática con el diagnóstico IA
            evaluacion_ia = EvaluacionCreate(
                solicitud_id=solicitud_id,
                diagnostico=diagnostico_data.get("diagnostico", "Diagnóstico por IA"),
                gravedad=diagnostico_data.get("gravedad", "media"),
                tiempo_estimado_reparacion=diagnostico_data.get("tiempo_estimado_minutos", 60),
                costo_estimado=0,  # Se calculará después con repuestos
                repuestos_necesarios=diagnostico_data.get("repuestos_sugeridos", []),
                requiere_grua=diagnostico_data.get("requiere_grua", False),
                notas_internas=f"Diagnóstico generado por IA ({resultado.get('modelo_usado', 'unknown')})",
                evaluador_id="sistema-ia",  # ID especial para el sistema IA
            )

            # Guardar la evaluación
            evaluacion_guardada = evaluaciones_storage.create(evaluacion_ia.model_dump())

            return DiagnosticoIAResponse(
                diagnostico=diagnostico_data,
                modelo_usado=resultado.get("modelo_usado", "unknown"),
                tokens_usados=resultado.get("tokens_usados", 0),
                solicitud_id=solicitud_id,
            )
        else:
            raise HTTPException(
                status_code=503,
                detail=f"Error del servicio de IA: {resultado.get('error')}"
            )

    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando diagnóstico: {str(e)}"
        )
