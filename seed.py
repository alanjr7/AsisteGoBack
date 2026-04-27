import os
import uuid
import json
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def hash_password(password: str) -> str:
    # Hash simple compatible con el sistema (bcrypt)
    import bcrypt
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def seed():
    db = SessionLocal()
    try:
        print("--- Iniciando Seeder Masivo de AsisteGO ---")

        # 1. TALLERES
        talleres_data = [
            {
                "id": str(uuid.uuid4()),
                "nombre": "Taller Central Santa Cruz",
                "direccion": "Av. Busch, entre 2do y 3er Anillo",
                "telefono": "78012345",
                "email": "central@taller.com",
                "lat": -17.7761,
                "lng": -63.1951,
                "descripcion": "Especialistas en mecánica general y electrónica automotriz.",
                "calificacion": 4.8
            },
            {
                "id": str(uuid.uuid4()),
                "nombre": "Mecánica El Palmar",
                "direccion": "Av. Santos Dumont, Calle 5",
                "telefono": "70098765",
                "email": "palmar@taller.com",
                "lat": -17.8285,
                "lng": -63.1805,
                "descripcion": "Servicio rápido, grúas 24/7 y auxilio mecánico.",
                "calificacion": 4.5
            },
            {
                "id": str(uuid.uuid4()),
                "nombre": "AutoTech Solutions",
                "direccion": "4to Anillo y Av. Banzer",
                "telefono": "71022334",
                "email": "autotech@taller.com",
                "lat": -17.7450,
                "lng": -63.1720,
                "descripcion": "Tecnología de punta para diagnóstico de motores y sistemas híbridos.",
                "calificacion": 4.9
            },
            {
                "id": str(uuid.uuid4()),
                "nombre": "Grúas y Talleres del Sur",
                "direccion": "Doble Vía a la Guardia, Km 6",
                "telefono": "75066778",
                "email": "delsur@taller.com",
                "lat": -17.8500,
                "lng": -63.2200,
                "descripcion": "Especializados en vehículos pesados y remolques de larga distancia.",
                "calificacion": 4.2
            }
        ]

        for t in talleres_data:
            exists = db.execute(text("SELECT id FROM talleres WHERE nombre = :nombre"), {"nombre": t["nombre"]}).fetchone()
            if not exists:
                db.execute(text("""
                    INSERT INTO talleres (id, nombre, direccion, telefono, email, lat, lng, descripcion, calificacion, created_at, updated_at)
                    VALUES (:id, :nombre, :direccion, :telefono, :email, :lat, :lng, :descripcion, :calificacion, :now, :now)
                """), {**t, "now": datetime.now()})
                
                # Crear usuario para el taller
                db.execute(text("""
                    INSERT INTO users (email, nombre, password_hash, rol, tipo_usuario, taller_id, created_at, updated_at)
                    VALUES (:email, :nombre, :password_hash, 'encargado', 'taller', :taller_id, :now, :now)
                """), {
                    "email": t["email"],
                    "nombre": f"Encargado {t['nombre']}",
                    "password_hash": hash_password("password123"),
                    "taller_id": t["id"],
                    "now": datetime.now()
                })
                print(f"Taller y usuario creado: {t['nombre']}")
            else:
                t["id"] = exists[0]

        # 2. CLIENTES Y SUS USUARIOS
        clientes_data = [
            {
                "id": "cliente-juan-001",
                "nombre": "Juan Pérez",
                "telefono": "77011223",
                "email": "movil@gmail.com",
                "lat": -17.7833,
                "lng": -63.1821,
                "foto": "https://i.pravatar.cc/150?u=juan"
            },
            {
                "id": "cliente-maria-002",
                "nombre": "Maria Garcia",
                "telefono": "76055443",
                "email": "maria@gmail.com",
                "lat": -17.7950,
                "lng": -63.1750,
                "foto": "https://i.pravatar.cc/150?u=maria"
            }
        ]

        for c in clientes_data:
            exists = db.execute(text("SELECT id FROM clientes WHERE email = :email"), {"email": c["email"]}).fetchone()
            if not exists:
                db.execute(text("""
                    INSERT INTO clientes (id, nombre, telefono, email, lat, lng, foto, created_at, updated_at)
                    VALUES (:id, :nombre, :telefono, :email, :lat, :lng, :foto, :now, :now)
                """), {**c, "now": datetime.now()})
                
                db.execute(text("""
                    INSERT INTO users (email, nombre, password_hash, rol, tipo_usuario, created_at, updated_at)
                    VALUES (:email, :nombre, :password_hash, 'cliente', 'cliente', :now, :now)
                """), {
                    "email": c["email"],
                    "nombre": c["nombre"],
                    "password_hash": hash_password("password123"),
                    "now": datetime.now()
                })
                print(f"Cliente y usuario creado: {c['nombre']}")
            else:
                c["id"] = exists[0]

        # 3. VEHÍCULOS
        vehiculos_data = [
            {"id": str(uuid.uuid4()), "cliente_id": "cliente-juan-001", "marca": "Toyota", "modelo": "Corolla", "anio": 2020, "placa": "ABC-123", "color": "Blanco"},
            {"id": str(uuid.uuid4()), "cliente_id": "cliente-juan-001", "marca": "Suzuki", "modelo": "Vitara", "anio": 2018, "placa": "XYZ-789", "color": "Rojo"},
            {"id": str(uuid.uuid4()), "cliente_id": "cliente-juan-001", "marca": "Honda", "modelo": "Civic", "anio": 2021, "placa": "HND-001", "color": "Negro"},
            {"id": str(uuid.uuid4()), "cliente_id": "cliente-maria-002", "marca": "Nissan", "modelo": "Sentra", "anio": 2022, "placa": "MNP-456", "color": "Azul"}
        ]

        for v in vehiculos_data:
            exists = db.execute(text("SELECT id FROM vehiculos WHERE placa = :placa"), {"placa": v["placa"]}).fetchone()
            if not exists:
                db.execute(text("""
                    INSERT INTO vehiculos (id, cliente_id, marca, modelo, anio, placa, color, tipo, activo, created_at, updated_at)
                    VALUES (:id, :cliente_id, :marca, :modelo, :anio, :placa, :color, 'Sedán', true, :now, :now)
                """), {**v, "now": datetime.now()})

        # 4. PERSONAL
        for t in talleres_data:
            roles = ["mecanico", "electrico", "grua"]
            for i in range(3):
                p_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO personal (id, nombre, rol, estado, taller_id, created_at, updated_at)
                    VALUES (:id, :nombre, :rol, 'disponible', :taller_id, :now, :now)
                """), {
                    "id": p_id,
                    "nombre": f"Técnico {i+1} - {t['nombre']}",
                    "rol": random.choice(roles),
                    "taller_id": t["id"],
                    "now": datetime.now()
                })

        # 5. REPUESTOS (15 por taller)
        categorias = ["Motor", "Frenos", "Suspensión", "Eléctrico", "Neumáticos", "Mantenimiento"]
        nombres_repuestos = [
            "Pastillas de Freno", "Disco de Freno", "Amortiguador Delantero", "Amortiguador Trasero",
            "Bujía Iridium", "Filtro de Aceite", "Filtro de Aire", "Batería 12V", "Alternador",
            "Correa de Distribución", "Radiador", "Bomba de Agua", "Sensor de Oxígeno",
            "Aceite Sintético 5W30", "Líquido de Frenos"
        ]

        for t in talleres_data:
            for nombre in nombres_repuestos:
                db.execute(text("""
                    INSERT INTO repuestos (id, taller_id, nombre, descripcion, precio, disponible, categoria, stock, created_at, updated_at)
                    VALUES (:id, :taller_id, :nombre, :descripcion, :precio, true, :categoria, :stock, :now, :now)
                """), {
                    "id": str(uuid.uuid4()),
                    "taller_id": t["id"],
                    "nombre": f"{nombre} - {t['nombre'][:5]}",
                    "descripcion": f"{nombre} de alta calidad disponible en {t['nombre']}.",
                    "precio": round(random.uniform(50.0, 1500.0), 2),
                    "categoria": random.choice(categorias),
                    "stock": random.randint(5, 50),
                    "now": datetime.now()
                })

        # 6. SOLICITUDES (Masivo)
        print("Generando solicitudes de reparación y grúa...")
        problemas_reparacion = [
            ("Frenos desgastados", "Cambio de pastillas y discos"),
            ("Motor no arranca", "Revisión de sistema eléctrico y batería"),
            ("Ruidos en la suspensión", "Cambio de amortiguadores y bujes"),
            ("Calentamiento de motor", "Limpieza de radiador y cambio de termostato"),
            ("Pérdida de potencia", "Limpieza de inyectores y cambio de bujías"),
            ("Fuga de aceite", "Cambio de empaquetadura de cárter"),
            ("Dirección dura", "Revisión de bomba hidráulica"),
            ("Check Engine encendido", "Escaneo computarizado y corrección de sensores")
        ]
        
        problemas_grua = [
            ("Accidente vial", "Remolque por colisión"),
            ("Llanta pinchada sin repuesto", "Traslado a gomería cercana"),
            ("Falla eléctrica total", "Traslado a taller especializado"),
            ("Atascado en barro/arena", "Rescate y remolque"),
            ("Sin combustible", "Auxilio y traslado a gasolinera"),
            ("Problema de caja", "Traslado por vehículo inmovilizado")
        ]

        # 15 Reparaciones para Juan
        for i in range(15):
            prob, desc = random.choice(problemas_reparacion)
            sol_id = str(uuid.uuid4())
            taller = random.choice(talleres_data)
            status = "FINALIZADA" if i < 12 else random.choice(["PENDIENTE", "REPARANDO", "ACEPTADA"])
            date = datetime.now() - timedelta(days=random.randint(1, 60), hours=random.randint(1, 23))
            
            db.execute(text("""
                INSERT INTO solicitudes (id, cliente_id, taller_id, vehiculo_marca, vehiculo_modelo, vehiculo_anio, vehiculo_placa, vehiculo_color, 
                                       descripcion, problema, estado, tipo, monto_pago, estado_pago, created_at, updated_at)
                VALUES (:id, :cliente_id, :taller_id, :marca, :modelo, :anio, :placa, :color, 
                        :descripcion, :problema, :estado, 'NORMAL', :monto, :estado_pago, :date, :date)
            """), {
                "id": sol_id,
                "cliente_id": "cliente-juan-001",
                "taller_id": taller["id"],
                "marca": "Toyota", "modelo": "Corolla", "anio": 2020, "placa": "ABC-123", "color": "Blanco",
                "descripcion": desc, "problema": prob,
                "estado": status,
                "monto": round(random.uniform(200, 2000), 2) if status == "FINALIZADA" else None,
                "estado_pago": "completado" if status == "FINALIZADA" else "pendiente",
                "date": date
            })
            
            if status == "FINALIZADA":
                monto = round(random.uniform(200, 2000), 2)
                db.execute(text("""
                    INSERT INTO facturas (id, solicitud_id, cliente_id, monto, comision, total, metodo_pago, enviada, created_at, updated_at)
                    VALUES (:id, :sol_id, :cli_id, :monto, :com, :total, :metodo, true, :date, :date)
                """), {
                    "id": str(uuid.uuid4()), "sol_id": sol_id, "cli_id": "cliente-juan-001",
                    "monto": monto, "com": monto * 0.1, "total": monto * 1.1,
                    "metodo": random.choice(["tarjeta", "qr", "efectivo"]),
                    "date": date + timedelta(hours=3)
                })

        # 12 Grúas para Juan
        for i in range(12):
            prob, desc = random.choice(problemas_grua)
            sol_id = str(uuid.uuid4())
            taller = random.choice(talleres_data)
            status = "FINALIZADA" if i < 10 else random.choice(["EN_CAMINO", "ACEPTADA", "PENDIENTE"])
            date = datetime.now() - timedelta(days=random.randint(1, 60), hours=random.randint(1, 23))
            
            db.execute(text("""
                INSERT INTO solicitudes (id, cliente_id, taller_id, vehiculo_marca, vehiculo_modelo, vehiculo_anio, vehiculo_placa, vehiculo_color, 
                                       descripcion, problema, estado, tipo, monto_pago, estado_pago, created_at, updated_at)
                VALUES (:id, :cliente_id, :taller_id, :marca, :modelo, :anio, :placa, :color, 
                        :descripcion, :problema, :estado, 'GRUA', :monto, :estado_pago, :date, :date)
            """), {
                "id": sol_id,
                "cliente_id": "cliente-juan-001",
                "taller_id": taller["id"],
                "marca": "Suzuki", "modelo": "Vitara", "anio": 2018, "placa": "XYZ-789", "color": "Rojo",
                "descripcion": desc, "problema": prob,
                "estado": status,
                "monto": round(random.uniform(150, 600), 2) if status == "FINALIZADA" else None,
                "estado_pago": "completado" if status == "FINALIZADA" else "pendiente",
                "date": date
            })
            
            if status == "FINALIZADA":
                monto = round(random.uniform(150, 600), 2)
                db.execute(text("""
                    INSERT INTO facturas (id, solicitud_id, cliente_id, monto, comision, total, metodo_pago, enviada, created_at, updated_at)
                    VALUES (:id, :sol_id, :cli_id, :monto, :com, :total, :metodo, true, :date, :date)
                """), {
                    "id": str(uuid.uuid4()), "sol_id": sol_id, "cli_id": "cliente-juan-001",
                    "monto": monto, "com": monto * 0.1, "total": monto * 1.1,
                    "metodo": random.choice(["qr", "efectivo"]),
                    "date": date + timedelta(hours=1)
                })

        db.commit()
        print("--- Seeder Masivo completado con éxito ---")

    except Exception as e:
        print(f"Error en el seeder: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
