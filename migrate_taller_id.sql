-- Migración para agregar soporte multi-taller
-- Ejecutar este script en PostgreSQL para agregar las columnas faltantes

-- 1. Crear tabla talleres
CREATE TABLE IF NOT EXISTS talleres (
    id VARCHAR(36) PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    direccion VARCHAR(500),
    telefono VARCHAR(50),
    email VARCHAR(255),
    lat FLOAT DEFAULT 0.0,
    lng FLOAT DEFAULT 0.0,
    descripcion TEXT,
    calificacion FLOAT DEFAULT 0.0,
    total_servicios INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Agregar columna taller_id a users
ALTER TABLE users ADD COLUMN IF NOT EXISTS taller_id VARCHAR(36);
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS fk_users_taller FOREIGN KEY (taller_id) REFERENCES talleres(id);

-- 3. Agregar columna taller_id a solicitudes
ALTER TABLE solicitudes ADD COLUMN IF NOT EXISTS taller_id VARCHAR(36);
ALTER TABLE solicitudes ADD CONSTRAINT IF NOT EXISTS fk_solicitudes_taller FOREIGN KEY (taller_id) REFERENCES talleres(id);

-- 4. Agregar columna taller_id a personal
ALTER TABLE personal ADD COLUMN IF NOT EXISTS taller_id VARCHAR(36);
ALTER TABLE personal ADD CONSTRAINT IF NOT EXISTS fk_personal_taller FOREIGN KEY (taller_id) REFERENCES talleres(id);

-- 5. Agregar columna taller_id a repuestos
ALTER TABLE repuestos ADD COLUMN IF NOT EXISTS taller_id VARCHAR(36);
ALTER TABLE repuestos ADD CONSTRAINT IF NOT EXISTS fk_repuestos_taller FOREIGN KEY (taller_id) REFERENCES talleres(id);

-- 6. Crear un taller por defecto para datos existentes
INSERT INTO talleres (id, nombre, email, created_at, updated_at)
VALUES ('taller-default-001', 'Taller Principal', 'taller@asistego.com', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;

-- 7. Asignar todos los usuarios existentes al taller por defecto
UPDATE users SET taller_id = 'taller-default-001' WHERE taller_id IS NULL;

-- 8. Asignar todas las solicitudes existentes al taller por defecto
UPDATE solicitudes SET taller_id = 'taller-default-001' WHERE taller_id IS NULL;

-- 9. Asignar todo el personal existente al taller por defecto
UPDATE personal SET taller_id = 'taller-default-001' WHERE taller_id IS NULL;

-- 10. Asignar todos los repuestos existentes al taller por defecto
UPDATE repuestos SET taller_id = 'taller-default-001' WHERE taller_id IS NULL;

-- Crear índices para mejor rendimiento
CREATE INDEX IF NOT EXISTS idx_users_taller_id ON users(taller_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_taller_id ON solicitudes(taller_id);
CREATE INDEX IF NOT EXISTS idx_personal_taller_id ON personal(taller_id);
CREATE INDEX IF NOT EXISTS idx_repuestos_taller_id ON repuestos(taller_id);
