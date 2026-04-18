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

router = APIRouter()

# Directorio base para uploads
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
IMAGES_DIR = os.path.join(UPLOAD_DIR, "images")
AUDIO_DIR = os.path.join(UPLOAD_DIR, "audio")
COMPROBANTES_DIR = os.path.join(UPLOAD_DIR, "comprobantes")

# Crear directorios si no existen
for dir_path in [UPLOAD_DIR, IMAGES_DIR, AUDIO_DIR, COMPROBANTES_DIR]:
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
    if folder not in ["images", "audio", "comprobantes"]:
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
    
    if folder not in ["images", "audio", "comprobantes"]:
        raise HTTPException(status_code=400, detail="Carpeta no válida")
    
    file_path = os.path.join(UPLOAD_DIR, folder, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    try:
        os.remove(file_path)
        return {"success": True, "message": "Archivo eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar: {str(e)}")
