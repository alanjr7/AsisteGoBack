"""
Servicio para integración con Supabase Storage.
Maneja subida de imágenes, audios y comprobantes PDF.
"""
import os
import uuid
from datetime import datetime
from utils.timezone import get_now
from typing import Optional, Tuple
import shutil
import io
import tempfile

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    print("[SUPABASE] Variables de entorno cargadas desde .env")
except ImportError:
    print("[SUPABASE] Advertencia: python-dotenv no está instalado. Variables de entorno pueden no cargarse.")

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("[SUPABASE] Advertencia: supabase no está instalado. Usando solo almacenamiento local.")

# Configuración desde variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "asistego_cubo"

def get_supabase_client() -> Optional[Client]:
    """Obtener cliente de Supabase si está configurado."""
    global SUPABASE_URL, SUPABASE_KEY
    
    if not SUPABASE_AVAILABLE:
        return None
    
    # Re-intentar cargar si están vacías
    if not SUPABASE_URL or not SUPABASE_KEY:
        load_dotenv(override=True)
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    
    try:
        # Algunos entornos pueden tener problemas con espacios en blanco
        url = SUPABASE_URL.strip()
        key = SUPABASE_KEY.strip()
        client = create_client(url, key)
        return client
    except Exception as e:
        print(f"[SUPABASE] Error al crear cliente: {e}")
        return None


def generate_unique_filename(original_filename: str) -> str:
    """Genera un nombre de archivo único con timestamp y UUID."""
    ext = os.path.splitext(original_filename)[1].lower()
    timestamp = get_now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}{ext}"


async def upload_image_to_supabase(file_content: bytes, filename: str) -> str:
    """
    Subir imagen a Supabase Storage.
    
    Args:
        file_content: Contenido del archivo en bytes
        filename: Nombre del archivo
    
    Returns:
        URL pública del archivo subido
    
    Raises:
        Exception: Si Supabase no está disponible o falla la subida
    """
    client = get_supabase_client()
    if not client:
        raise Exception("Supabase no disponible")
    
    file_path = f"images/{filename}"
    
    try:
        response = client.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": "image/jpeg"}
        )
        
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        print(f"[SUPABASE] Imagen subida exitosamente: {filename}")
        return public_url
    except Exception as e:
        print(f"[SUPABASE] Error al subir imagen: {e}")
        raise


async def upload_audio_to_supabase(file_content: bytes, filename: str) -> str:
    """
    Subir audio a Supabase Storage.
    
    Args:
        file_content: Contenido del archivo en bytes
        filename: Nombre del archivo
    
    Returns:
        URL pública del archivo subido
    
    Raises:
        Exception: Si Supabase no está disponible o falla la subida
    """
    client = get_supabase_client()
    if not client:
        raise Exception("Supabase no disponible")
    
    file_path = f"audio/{filename}"
    
    try:
        response = client.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": "audio/mpeg"}
        )
        
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        print(f"[SUPABASE] Audio subido exitosamente: {filename}")
        return public_url
    except Exception as e:
        print(f"[SUPABASE] Error al subir audio: {e}")
        raise


async def upload_profile_to_supabase(file_content: bytes, filename: str) -> str:
    """
    Subir foto de perfil a Supabase Storage.
    
    Args:
        file_content: Contenido del archivo en bytes
        filename: Nombre del archivo
    
    Returns:
        URL pública del archivo subido
    
    Raises:
        Exception: Si Supabase no está disponible o falla la subida
    """
    client = get_supabase_client()
    if not client:
        raise Exception("Supabase no disponible")
    
    file_path = f"perfiles/{filename}"
    
    try:
        response = client.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": "image/jpeg"}
        )
        
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        print(f"[SUPABASE] Foto de perfil subida exitosamente: {filename}")
        return public_url
    except Exception as e:
        print(f"[SUPABASE] Error al subir foto de perfil: {e}")
        raise


async def delete_file_from_supabase(file_path: str) -> None:
    """
    Eliminar archivo de Supabase Storage.
    
    Args:
        file_path: Ruta del archivo en el bucket (ej: "images/filename.jpg")
    
    Raises:
        Exception: Si Supabase no está disponible o falla la eliminación
    """
    client = get_supabase_client()
    if not client:
        raise Exception("Supabase no disponible")
    
    client.storage.from_(BUCKET_NAME).remove([file_path])
    print(f"[SUPABASE] Archivo eliminado: {file_path}")




async def upload_image(file_content: bytes, filename: str) -> str:
    """
    Subir imagen a Supabase Storage.
    
    Args:
        file_content: Contenido del archivo en bytes
        filename: Nombre del archivo
    
    Returns:
        URL pública del archivo subido
    """
    return await upload_image_to_supabase(file_content, filename)


async def upload_audio(file_content: bytes, filename: str) -> str:
    """
    Subir audio a Supabase Storage.
    
    Args:
        file_content: Contenido del archivo en bytes
        filename: Nombre del archivo
    
    Returns:
        URL pública del archivo subido
    """
    return await upload_audio_to_supabase(file_content, filename)


async def upload_profile(file_content: bytes, filename: str) -> str:
    """
    Subir foto de perfil a Supabase Storage.
    
    Args:
        file_content: Contenido del archivo en bytes
        filename: Nombre del archivo
    
    Returns:
        URL pública del archivo subido
    """
    return await upload_profile_to_supabase(file_content, filename)


def is_supabase_url(url: str) -> bool:
    """
    Verificar si una URL es de Supabase.
    
    Args:
        url: URL a verificar
    
    Returns:
        True si es URL de Supabase, False si es local
    """
    return "supabase.co" in url or "rtanssfbvhpstvfsmghj" in url


def extract_file_path_from_url(url: str) -> Optional[str]:
    """
    Extraer la ruta del archivo desde una URL de Supabase.
    
    Args:
        url: URL de Supabase
    
    Returns:
        Ruta del archivo en el bucket o None si no es URL de Supabase
    """
    if not is_supabase_url(url):
        return None
    
    try:
        parts = url.split("/")
        bucket_index = parts.index(BUCKET_NAME) if BUCKET_NAME in parts else -1
        if bucket_index != -1 and bucket_index + 1 < len(parts):
            return "/".join(parts[bucket_index + 1:])
    except Exception as e:
        print(f"[SUPABASE] Error al extraer ruta de URL: {e}")
    
    return None


async def upload_comprobante_to_supabase(file_content: bytes, filename: str, content_type: str = "application/pdf") -> str:
    """
    Subir comprobante (PDF o imagen) a Supabase Storage.
    
    Args:
        file_content: Contenido del archivo en bytes
        filename: Nombre del archivo
        content_type: Tipo MIME del archivo (default: application/pdf)
    
    Returns:
        URL pública del archivo subido
    
    Raises:
        Exception: Si Supabase no está disponible o falla la subida
    """
    client = get_supabase_client()
    if not client:
        raise Exception("Supabase no disponible")
    
    file_path = f"comprobantes/{filename}"
    
    try:
        response = client.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": content_type}
        )
        
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        print(f"[SUPABASE] Comprobante subido exitosamente: {filename}")
        return public_url
    except Exception as e:
        print(f"[SUPABASE] Error al subir comprobante: {e}")
        raise

def ensure_full_url(path: Optional[str]) -> Optional[str]:
    """
    Asegura que una ruta sea una URL completa.
    Si es relativa, le añade el BACKEND_URL.
    """
    if not path:
        return None
    
    if path.startswith("http://") or path.startswith("https://"):
        return path
    
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
    
    # Asegurar que la ruta comience con / si es relativa
    if not path.startswith("/"):
        path = f"/{path}"
        
    return f"{backend_url}{path}"
