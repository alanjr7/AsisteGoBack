"""
Router para manejo de archivos: evidencias (fotos, audios) y comprobantes de pago.
Almacenamiento local en directorio uploads/.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.responses import FileResponse
from typing import Optional
import os
import shutil
from datetime import datetime
from utils.timezone import get_now
import uuid
import traceback

# Importar servicio de Supabase
try:
    from utils.supabase_storage import (
        upload_image,
        upload_audio,
        upload_profile,
        upload_comprobante_to_supabase,
        delete_file_from_supabase,
        is_supabase_url,
        extract_file_path_from_url,
        generate_unique_filename
    )
    SUPABASE_STORAGE_AVAILABLE = True
except ImportError as e:
    print(f"[UPLOAD] Advertencia: No se pudo importar supabase_storage: {e}")
    SUPABASE_STORAGE_AVAILABLE = False

# Importaciones para foto de perfil
try:
    from database_sql import get_db, Taller, Cliente
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
async def upload_image_endpoint(
    file: UploadFile = File(...),
    descripcion: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None)
):
    """
    Subir una imagen (foto de evidencia) a Supabase Storage.
    Retorna la URL del archivo subido.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not SUPABASE_STORAGE_AVAILABLE:
        raise HTTPException(status_code=500, detail="Supabase Storage no está configurado")
    
    try:
        validate_file(file, ALLOWED_IMAGE_TYPES)
        
        file_content = await file.read()
        filename = generate_unique_filename(file.filename or "image.jpg")
        
        url = await upload_image(file_content, filename)
        
        return {
            "success": True,
            "url": url,
            "filename": filename,
            "tipo": "imagen",
            "descripcion": descripcion,
            "storage": "supabase"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir imagen: {str(e)}")


@router.post("/audio")
async def upload_audio_endpoint(
    file: UploadFile = File(...),
    descripcion: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None)
):
    """
    Subir un archivo de audio (grabación de evidencia) a Supabase Storage.
    Retorna la URL del archivo subido.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not SUPABASE_STORAGE_AVAILABLE:
        raise HTTPException(status_code=500, detail="Supabase Storage no está configurado")
    
    try:
        validate_file(file, ALLOWED_AUDIO_TYPES)
        
        file_content = await file.read()
        filename = generate_unique_filename(file.filename or "audio.mp3")
        
        url = await upload_audio(file_content, filename)
        
        return {
            "success": True,
            "url": url,
            "filename": filename,
            "tipo": "audio",
            "descripcion": descripcion,
            "storage": "supabase"
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
    Subir un comprobante de pago (imagen o PDF) a Supabase Storage.
    Retorna la URL del archivo subido.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not SUPABASE_STORAGE_AVAILABLE:
        raise HTTPException(status_code=500, detail="Supabase Storage no está configurado")
    
    try:
        allowed_types = ALLOWED_IMAGE_TYPES | ALLOWED_PDF_TYPES
        validate_file(file, allowed_types)
        
        file_content = await file.read()
        filename = generate_unique_filename(file.filename or "comprobante.pdf")
        
        content_type = file.content_type or "application/pdf"
        url = await upload_comprobante_to_supabase(file_content, filename, content_type)
        
        return {
            "success": True,
            "url": url,
            "filename": filename,
            "solicitud_id": solicitud_id,
            "tipo": "comprobante",
            "storage": "supabase"
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
        # Verificar si es una URL de Supabase
        # Para simplificar, asumimos que si el archivo existe localmente, lo eliminamos localmente
        # Si no existe localmente pero es una URL de Supabase, intentamos eliminar de Supabase
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"success": True, "message": "Archivo eliminado (local)"}
        else:
            # Intentar eliminar de Supabase si la URL parece ser de Supabase
            # Nota: Este endpoint necesita la URL completa, no solo el filename
            # Por ahora, solo soportamos eliminación local
            return {"success": True, "message": "Archivo no encontrado localmente (puede estar en Supabase)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar: {str(e)}")


# ==================== FOTO DE PERFIL ====================

@router.put("/taller/perfil/foto")
async def update_taller_profile_photo(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Actualizar foto de perfil del taller en Supabase Storage."""
    return await _update_any_profile_photo(file, authorization, "taller")

@router.put("/cliente/perfil/foto")
async def update_cliente_profile_photo(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Actualizar foto de perfil del cliente en Supabase Storage."""
    return await _update_any_profile_photo(file, authorization, "cliente")

async def _update_any_profile_photo(file: UploadFile, authorization: Optional[str], user_type: str):
    """Lógica común para actualizar foto de perfil (taller o cliente)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    if not SUPABASE_STORAGE_AVAILABLE:
        raise HTTPException(status_code=500, detail="Supabase Storage no está configurado")
    
    if not all([get_db, Taller, Cliente, decode_access_token]):
        raise HTTPException(status_code=500, detail="Error de configuración del servidor")
    
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Formato de token inválido")
        
        token = authorization.replace("Bearer ", "")
        payload = decode_access_token(token)
        
        if not payload:
            raise HTTPException(status_code=401, detail="Token inválido o expirado")
        
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        validate_file(file, ALLOWED_IMAGE_TYPES, max_size=5*1024*1024)
        
        ext = os.path.splitext(file.filename)[1].lower()
        timestamp = get_now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"perfil_{user_type}_{unique_id}_{timestamp}{ext}"
        
        file_content = await file.read()
        url = await upload_profile(file_content, filename)
        
        db = next(get_db())
        try:
            entity = None
            if user_type == "taller":
                taller_id = payload.get("taller_id")
                if not taller_id:
                    raise HTTPException(status_code=401, detail="No se encontró taller_id en el token")
                entity = db.query(Taller).filter(Taller.id == taller_id).first()
            else:
                entity = db.query(Cliente).filter(Cliente.email == email).first()
            
            if not entity:
                raise HTTPException(status_code=404, detail=f"{user_type.capitalize()} no encontrado")
            
            # Eliminar foto anterior si existe
            if entity.foto:
                if is_supabase_url(entity.foto):
                    old_path = extract_file_path_from_url(entity.foto)
                    if old_path:
                        try:
                            await delete_file_from_supabase(old_path)
                        except: pass
                elif entity.foto.startswith("/uploads/perfiles/"):
                    old_path = os.path.join(PERFILES_DIR, entity.foto.split("/")[-1])
                    if os.path.exists(old_path):
                        try: os.remove(old_path)
                        except: pass
            
            entity.foto = url
            db.commit()
            
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
        print(f"[UPLOAD] ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar foto: {str(e)}")
