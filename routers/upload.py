"""
Router para manejo de archivos: evidencias (fotos, audios) y comprobantes de pago.
Almacenamiento local en directorio uploads/.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import FileResponse
from typing import Optional
import os
import shutil
from datetime import datetime
import uuid
import traceback

# Importaciones para foto de perfil
try:
    from database_sql import get_db, Taller
    from utils.security import decode_access_token
except ImportError as e:
    print(f"[UPLOAD] Advertencia: No se pudieron importar dependencias de BD: {e}")
    get_db = None
    Taller = None
    decode_access_token = None

router = APIRouter()

# Directorio base para uploads
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
IMAGES_DIR = os.path.join(UPLOAD_DIR, "images")
AUDIO_DIR = os.path.join(UPLOAD_DIR, "audio")
COMPROBANTES_DIR = os.path.join(UPLOAD_DIR, "comprobantes")
PERFILES_DIR = os.path.join(UPLOAD_DIR, "perfiles")

# Crear directorios si no existen
for dir_path in [UPLOAD_DIR, IMAGES_DIR, AUDIO_DIR, COMPROBANTES_DIR, PERFILES_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Tipos de archivo permitidos
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp3", "audio/mp4"}
ALLOWED_PDF_TYPES = {"application/pdf"}

# Tamaño máximo: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024


def generate_unique_filename(original_filename: str) -> str:
    """Genera un nombre de archivo único con timestamp y UUID."""
    ext = os.path.splitext(original_filename)[1].lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}{ext}"


def validate_file(file: UploadFile, allowed_types: set, max_size: int = MAX_FILE_SIZE) -> None:
    """Valida tipo y tamaño de archivo."""
    # Validar tipo
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Permitidos: {', '.join(allowed_types)}"
        )
    
    # Validar tamaño (se hará durante la lectura)
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo demasiado grande. Máximo: {max_size / (1024 * 1024)}MB"
        )


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    descripcion: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None)
):
    """
    Subir una imagen (foto de evidencia).
    Retorna la URL del archivo subido.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        validate_file(file, ALLOWED_IMAGE_TYPES)
        
        filename = generate_unique_filename(file.filename or "image.jpg")
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # Guardar archivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # URL relativa para acceder al archivo
        url = f"/uploads/images/{filename}"
        
        return {
            "success": True,
            "url": url,
            "filename": filename,
            "tipo": "imagen",
            "descripcion": descripcion
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir imagen: {str(e)}")


@router.post("/audio")
async def upload_audio(
    file: UploadFile = File(...),
    descripcion: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None)
):
    """
    Subir un archivo de audio (grabación de evidencia).
    Retorna la URL del archivo subido.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        validate_file(file, ALLOWED_AUDIO_TYPES)
        
        filename = generate_unique_filename(file.filename or "audio.mp3")
        file_path = os.path.join(AUDIO_DIR, filename)
        
        # Guardar archivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        url = f"/uploads/audio/{filename}"
        
        return {
            "success": True,
            "url": url,
            "filename": filename,
            "tipo": "audio",
            "descripcion": descripcion
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir audio: {str(e)}")


@router.post("/comprobante")
async def upload_comprobante(
    file: UploadFile = File(...),
    solicitud_id: str = Form(...),
    authorization: Optional[str] = Header(None)
):
    """
    Subir un comprobante de pago (imagen o PDF).
    Retorna la URL del archivo subido.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        allowed_types = ALLOWED_IMAGE_TYPES | ALLOWED_PDF_TYPES
        validate_file(file, allowed_types)
        
        filename = generate_unique_filename(file.filename or "comprobante.jpg")
        file_path = os.path.join(COMPROBANTES_DIR, filename)
        
        # Guardar archivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        url = f"/uploads/comprobantes/{filename}"
        
        return {
            "success": True,
            "url": url,
            "filename": filename,
            "solicitud_id": solicitud_id,
            "tipo": "comprobante"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir comprobante: {str(e)}")


@router.get("/file/{folder}/{filename}")
async def get_file(folder: str, filename: str):
    """
    Servir un archivo estático (imagen, audio o comprobante).
    """
    # Validar que la carpeta sea válida
    if folder not in ["images", "audio", "comprobantes", "perfiles"]:
        raise HTTPException(status_code=400, detail="Carpeta no válida")
    
    file_path = os.path.join(UPLOAD_DIR, folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    # Determinar content type
    ext = os.path.splitext(filename)[1].lower()
    content_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".pdf": "application/pdf"
    }
    content_type = content_type_map.get(ext, "application/octet-stream")
    
    return FileResponse(file_path, media_type=content_type)


@router.delete("/file/{folder}/{filename}")
async def delete_file(
    folder: str,
    filename: str,
    authorization: Optional[str] = Header(None)
):
    """
    Eliminar un archivo.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if folder not in ["images", "audio", "comprobantes", "perfiles"]:
        raise HTTPException(status_code=400, detail="Carpeta no válida")
    
    file_path = os.path.join(UPLOAD_DIR, folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    try:
        os.remove(file_path)
        return {"success": True, "message": "Archivo eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar: {str(e)}")


# ==================== FOTO DE PERFIL ====================

@router.put("/taller/perfil/foto")
async def update_profile_photo(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """
    Actualizar foto de perfil del taller.
    Requiere token de autorización.
    Retorna la URL de la nueva foto.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    # Verificar que las importaciones estén disponibles
    if not all([get_db, Taller, decode_access_token]):
        raise HTTPException(status_code=500, detail="Error de configuración del servidor: dependencias no disponibles")
    
    try:
        # Decodificar token para obtener taller_id
        token = authorization.replace("Bearer ", "")
        payload = decode_access_token(token)
        
        if not payload:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        taller_id = payload.get("taller_id")
        if not taller_id:
            raise HTTPException(status_code=401, detail="No se encontró información del taller")
        
        print(f"[UPLOAD] Actualizando foto para taller: {taller_id}")
        
        # Validar archivo
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de imagen no permitido. Permitidos: JPEG, PNG, WEBP"
            )
        
        # Validar tamaño (5MB máximo para perfiles)
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="La imagen no debe superar 5MB")
        
        # Generar nombre único con ID del taller
        ext = os.path.splitext(file.filename)[1].lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"perfil_{taller_id}_{timestamp}{ext}"
        file_path = os.path.join(PERFILES_DIR, filename)
        
        print(f"[UPLOAD] Guardando archivo: {file_path}")
        
        # Guardar archivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # URL relativa
        url = f"/uploads/perfiles/{filename}"
        
        print(f"[UPLOAD] Actualizando base de datos...")
        
        # Actualizar en base de datos
        db = next(get_db())
        try:
            taller = db.query(Taller).filter(Taller.id == taller_id).first()
            if not taller:
                raise HTTPException(status_code=404, detail="Taller no encontrado")
            
            # Eliminar foto anterior si existe
            if taller.foto and taller.foto.startswith("/uploads/perfiles/"):
                old_filename = taller.foto.replace("/uploads/perfiles/", "")
                old_path = os.path.join(PERFILES_DIR, old_filename)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                        print(f"[UPLOAD] Foto anterior eliminada: {old_path}")
                    except Exception as e:
                        print(f"[UPLOAD] No se pudo eliminar foto anterior: {e}")
            
            # Actualizar con nueva foto
            taller.foto = url
            db.commit()
            print(f"[UPLOAD] Foto actualizada en BD: {url}")
            
        finally:
            db.close()
        
        return {
            "success": True,
            "url": url,
            "message": "Foto de perfil actualizada exitosamente"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[UPLOAD] ERROR: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar foto: {str(e)}")
