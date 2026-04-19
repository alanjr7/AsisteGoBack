"""Configuración de rate limiting para la API."""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response

# Limiter principal - usa IP como clave por defecto
limiter = Limiter(key_func=get_remote_address)


# Límites específicos para endpoints de IA
IA_RATE_LIMIT = "10/minute"  # 10 requests por minuto por IP
IA_BURST_LIMIT = "5/minute"  # Para diagnósticos IA más costosos


def get_user_id(request: Request) -> str:
    """Obtener ID de usuario para rate limiting (si está autenticado)."""
    # Intentar obtener user_id del estado de la request (seteado por auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


# Limiter por usuario autenticado
user_limiter = Limiter(key_func=get_user_id)
