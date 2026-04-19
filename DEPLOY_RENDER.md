# Guía de Despliegue en Render con PostgreSQL

## Paso 1: Preparar el código

El código ya está configurado. Los cambios hechos:
- `database_sql.py` ahora maneja correctamente URLs de Render
- Se agregó SSL requerido para conexiones externas
- Se creó `render.yaml` para configuración de infraestructura

## Paso 2: Crear Base de Datos PostgreSQL en Render

1. Ve a [dashboard.render.com](https://dashboard.render.com)
2. Click en **New** → **PostgreSQL**
3. Configuración:
   - **Name**: `asistego-db` (o el nombre que prefieras)
   - **Database**: `asistego`
   - **User**: `asistego`
   - **Plan**: Free (o el que necesites)
4. Click **Create Database**
5. Espera a que esté disponible (estado "Available")

## Paso 3: Obtener la URL de conexión

1. Entra a tu base de datos creada
2. Busca **External Connection String** (URL externa)
3. Copia la URL completa (ejemplo: `postgres://asistego:password@host.render.com:5432/asistego`)

## Paso 4: Crear Web Service

1. En Render dashboard, click **New** → **Web Service**
2. Conecta tu repositorio de GitHub/GitLab
3. Configuración:
   - **Name**: `asistego-api`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Paso 5: Configurar Variables de Entorno

En la sección **Environment** del Web Service, agrega:

```
DATABASE_URL=postgres://asistego:TU_PASSWORD@TU_HOST.render.com:5432/asistego
SECRET_KEY=tu-clave-secreta-super-segura-2024
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
OPENROUTER_API_KEY=sk-or-v1-tu-api-key
```

**Importante**: Usa la **External Connection String** copiada en el Paso 3.

## Paso 6: Deploy

1. Click en **Deploy**
2. Render construirá y desplegará automáticamente
3. Verifica los logs para confirmar conexión exitosa

## Verificar el despliegue

Una vez desplegado, prueba estos endpoints:

```
https://TU-SERVICIO.onrender.com/
https://TU-SERVICIO.onrender.com/health
https://TU-SERVICIO.onrender.com/db-check
```

## Solución de problemas

### Error de conexión a base de datos
- Verifica que `DATABASE_URL` esté configurada correctamente
- Asegúrate de usar la **External Connection String**, no la Internal
- Verifica que la base de datos esté en estado "Available"

### Puerto no detectado
- Asegúrate de que el comando de inicio use `--port $PORT`
- No hardcodees un puerto específico

### Migraciones fallidas
- Las tablas se crean automáticamente al iniciar
- Si hay errores, revisa los logs en Render
