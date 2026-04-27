"""
Script de migración para agregar columna analisis_ia a la tabla solicitudes.
Ejecutar: python migrar_analisis_ia.py
"""
from sqlalchemy import create_engine, text
from database_sql import get_database_url, engine

def migrate():
    try:
        with engine.connect() as conn:
            # Verificar si la columna ya existe
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'solicitudes' AND column_name = 'analisis_ia';
            """))

            if result.fetchone():
                print("✅ La columna analisis_ia ya existe en la tabla solicitudes")
            else:
                # Agregar la columna
                conn.execute(text("""
                    ALTER TABLE solicitudes
                    ADD COLUMN analisis_ia TEXT;
                """))
                conn.commit()
                print("✅ Columna analisis_ia agregada exitosamente a la tabla solicitudes")

    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        raise

if __name__ == "__main__":
    migrate()
