#!/usr/bin/env python3
"""
Script para resetear la base de datos de Asistego.
Elimina todos los datos y recrea las tablas.
USAR CON PRECAUCIÓN - Se perderán todos los datos.
"""

from sqlalchemy import text
from database_sql import engine, Base

def reset_database():
    """Eliminar todas las tablas y recrearlas."""
    print("⚠️  ATENCIÓN: Esto eliminará TODOS los datos de la base de datos")
    print("🗑️  Eliminando tablas existentes...")
    
    # Obtener conexión
    with engine.connect() as conn:
        # Desactivar foreign keys temporalmente para poder eliminar tablas
        conn.execute(text("SET session_replication_role = 'replica';"))
        
        # Obtener lista de tablas
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result]
        
        # Eliminar cada tabla
        for table in tables:
            print(f"   🗑️  Eliminando tabla: {table}")
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
        
        conn.execute(text("SET session_replication_role = 'origin';"))
        conn.commit()
    
    print("✅ Tablas eliminadas")
    print("🏗️  Recreando tablas...")
    
    # Recrear todas las tablas
    Base.metadata.create_all(bind=engine)
    
    print("✅ Base de datos reseteada exitosamente")
    print("📝 Ahora puedes crear nuevos usuarios y datos limpios")

if __name__ == "__main__":
    confirm = input("¿Estás seguro de que quieres eliminar TODOS los datos? (escribe 'SI' para confirmar): ")
    if confirm == "SI":
        reset_database()
    else:
        print("❌ Operación cancelada")
