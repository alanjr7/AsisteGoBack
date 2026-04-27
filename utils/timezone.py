import pytz
from datetime import datetime

def get_now():
    """
    Retorna la fecha y hora actual en la zona horaria de Bolivia (GMT-4).
    Retorna un objeto naive (sin timezone info) para compatibilidad con la DB.
    """
    bolivia_tz = pytz.timezone('America/La_Paz')
    return datetime.now(bolivia_tz).replace(tzinfo=None)
