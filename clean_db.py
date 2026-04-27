
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    print("Limpiando tablas para re-poblar...")
    # El orden importa por las llaves foráneas
    tables = ['facturas', 'solicitud_personal', 'solicitudes', 'vehiculos', 'repuestos', 'personal', 'clientes', 'users', 'talleres']
    for table in tables:
        try:
            conn.execute(text(f"DELETE FROM {table}"))
            print(f"  Tabla {table} limpiada")
        except Exception as e:
            print(f"  Error limpiando {table}: {e}")
    conn.commit()
    print("Limpieza completada.")
