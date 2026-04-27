
import os
import uuid
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def populate():
    db = SessionLocal()
    try:
        # Obtener un taller existente
        taller = db.execute(text("SELECT id, nombre FROM talleres LIMIT 1")).fetchone()
        if not taller:
            print("❌ No hay talleres en la base de datos. Por favor crea uno primero.")
            return

        taller_id = taller[0]
        taller_nombre = taller[1]
        print(f"Poblando repuestos para el taller: {taller_nombre} ({taller_id})")

        repuestos = [
            {
                "nombre": "Pastillas de Freno Cerámicas",
                "descripcion": "Pastillas de freno de alta durabilidad para sedanes y SUVs. Reducen el ruido y el polvo.",
                "precio": 350.0,
                "imagen": "https://images.unsplash.com/photo-1486006396113-ad73c5946f0c?w=400",
                "disponible": True,
                "marca": "Bosch",
                "categoria": "Frenos",
                "stock": 15
            },
            {
                "nombre": "Filtro de Aceite Sintético",
                "descripcion": "Filtro de aceite premium compatible con motores modernos. Captura el 99% de impurezas.",
                "precio": 85.0,
                "imagen": "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?w=400",
                "disponible": True,
                "marca": "Mann Filter",
                "categoria": "Mantenimiento",
                "stock": 40
            },
            {
                "nombre": "Amortiguador Delantero Gas",
                "descripcion": "Amortiguador de gas para un manejo suave y estable. Diseñado para calles bacheadas.",
                "precio": 650.0,
                "imagen": "https://images.unsplash.com/photo-1621905252507-b35242f8df49?w=400",
                "disponible": True,
                "marca": "Monroe",
                "categoria": "Suspensión",
                "stock": 8
            },
            {
                "nombre": "Batería 12V 70Ah",
                "descripcion": "Batería de larga vida útil con alta capacidad de arranque en frío. Libre de mantenimiento.",
                "precio": 950.0,
                "imagen": "https://images.unsplash.com/photo-1582266255765-fa5cf1a1d501?w=400",
                "disponible": True,
                "marca": "Varta",
                "categoria": "Eléctrico",
                "stock": 5
            },
            {
                "nombre": "Bujía Iridium Power",
                "descripcion": "Bujía de iridio para mejor combustión y ahorro de combustible. Paquete de 4 unidades.",
                "precio": 220.0,
                "imagen": "https://images.unsplash.com/photo-1605164599901-f89248443976?w=400",
                "disponible": True,
                "marca": "Denso",
                "categoria": "Motor",
                "stock": 20
            }
        ]

        for r in repuestos:
            # Verificar si ya existe por nombre
            exists = db.execute(text("SELECT id FROM repuestos WHERE nombre = :nombre AND taller_id = :taller_id"), 
                               {"nombre": r["nombre"], "taller_id": taller_id}).fetchone()
            if not exists:
                repuesto_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO repuestos (id, taller_id, nombre, descripcion, precio, imagen, disponible, marca, categoria, vehiculos_compatibles, stock, stock_minimo, created_at, updated_at)
                    VALUES (:id, :taller_id, :nombre, :descripcion, :precio, :imagen, :disponible, :marca, :categoria, :vehiculos, :stock, :stock_minimo, :now, :now)
                """), {
                    "id": repuesto_id,
                    "taller_id": taller_id,
                    "nombre": r["nombre"],
                    "descripcion": r["descripcion"],
                    "precio": r["precio"],
                    "imagen": r["imagen"],
                    "disponible": r["disponible"],
                    "marca": r["marca"],
                    "categoria": r["categoria"],
                    "vehiculos": json.dumps(["Universal", "Toyota", "Suzuki"]),
                    "stock": r["stock"],
                    "stock_minimo": 5,
                    "now": datetime.now()
                })
                print(f"Agregado: {r['nombre']}")
            else:
                print(f"Ya existe: {r['nombre']}")
        
        db.commit()
        print("Proceso de población completado.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    populate()
