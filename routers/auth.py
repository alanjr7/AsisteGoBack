from fastapi import APIRouter, HTTPException, Header, Depends
from sqlalchemy.orm import Session
import uuid
from models import (
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse,
    ChangePasswordRequest, ChangePasswordResponse
)
from database_sql import get_db, User, Cliente, Taller
from database import db as memory_db
from utils.security import (
    hash_password, verify_password, create_access_token, decode_access_token
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
    x_platform: str = Header("web", alias="X-Platform")
):
    """Autenticar usuario y retornar token JWT. Valida plataforma (web vs mobile)."""
    # Buscar usuario en PostgreSQL
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    # Validar que el tipo de usuario corresponde a la plataforma
    if x_platform == "web" and user.tipo_usuario != "taller":
        raise HTTPException(
            status_code=403,
            detail="Los clientes solo pueden iniciar sesión en la app móvil"
        )
    
    if x_platform == "mobile" and user.tipo_usuario != "cliente":
        raise HTTPException(
            status_code=403,
            detail="Los usuarios de taller solo pueden iniciar sesión en la web"
        )
    
    # Crear token JWT con taller_id y tipo_usuario
    token = create_access_token(data={
        "sub": user.email,
        "nombre": user.nombre,
        "rol": user.rol,
        "taller_id": user.taller_id,
        "tipo_usuario": user.tipo_usuario
    })
    
    return LoginResponse(
        success=True,
        token=token,
        message="Login exitoso"
    )


@router.post("/register", response_model=RegisterResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Registrar nuevo usuario en MySQL."""
    print(f"📝 Registro recibido: nombre={data.nombre}, email={data.email}")

    try:
        # Verificar si el email ya existe
        existing_user = db.query(User).filter(User.email == data.email).first()
        if existing_user:
            print(f"⚠️ Email ya registrado: {data.email}")
            raise HTTPException(status_code=400, detail="El email ya está registrado")

        # Determinar tipo_usuario (por defecto "taller" para registro web)
        tipo_usuario = data.tipo_usuario or "taller"
        
        # Si no se especificó taller_id y es tipo taller, crear un nuevo taller automáticamente
        taller_id = data.taller_id
        if tipo_usuario == "taller" and not taller_id:
            nuevo_taller = Taller(
                id=str(uuid.uuid4()),
                nombre=f"Taller de {data.nombre}",
                email=data.email
            )
            db.add(nuevo_taller)
            db.commit()
            db.refresh(nuevo_taller)
            taller_id = nuevo_taller.id
            print(f"✅ Nuevo taller creado: ID={taller_id}")

        # Crear nuevo usuario con contraseña hasheada
        new_user = User(
            email=data.email,
            nombre=data.nombre,
            password_hash=hash_password(data.password),
            rol="encargado" if tipo_usuario == "taller" else "cliente",
            tipo_usuario=tipo_usuario,
            taller_id=taller_id if tipo_usuario == "taller" else None
        )
        print(f"🔄 Creando usuario: email={new_user.email}")
        db.add(new_user)
        print(f"💾 Ejecutando commit...")
        db.commit()
        print(f"✅ Commit exitoso")
        db.refresh(new_user)
        print(f"✅ Usuario guardado en MySQL: ID={new_user.id}, email={new_user.email}")

        # Crear cliente vinculado al usuario para que pueda hacer solicitudes
        cliente_id = str(uuid.uuid4())
        new_cliente = Cliente(
            id=cliente_id,
            nombre=data.nombre,
            telefono="",  # Se puede actualizar después
            email=data.email,
            foto=None,
            lat=0.0,
            lng=0.0,
            veces_atendido=0,
            calificacion_promedio=None
        )
        db.add(new_cliente)
        db.commit()
        print(f"✅ Cliente creado para usuario: ID={cliente_id}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR en registro: {type(e).__name__}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar usuario: {str(e)}")

    # Actualizar taller en memoria (mantener compatibilidad)
    if memory_db.taller:
        memory_db.taller["nombre"] = data.nombre
        memory_db.taller["email"] = data.email

    # Crear token JWT con taller_id
    token = create_access_token(data={
        "sub": new_user.email,
        "nombre": new_user.nombre,
        "rol": new_user.rol,
        "taller_id": new_user.taller_id
    })

    return RegisterResponse(
        success=True,
        token=token,
        message="Registro exitoso",
        user={
            "nombre": new_user.nombre,
            "email": new_user.email,
            "rol": new_user.rol,
            "tipo_usuario": new_user.tipo_usuario,
            "taller_id": new_user.taller_id
        }
    )


@router.post("/register-mobile", response_model=RegisterResponse)
def register_mobile(data: RegisterRequest, db: Session = Depends(get_db)):
    """Registrar nuevo cliente desde la app móvil."""
    print(f"📝 Registro móvil recibido: nombre={data.nombre}, email={data.email}")

    try:
        # Verificar si el email ya existe
        existing_user = db.query(User).filter(User.email == data.email).first()
        if existing_user:
            print(f"⚠️ Email ya registrado: {data.email}")
            raise HTTPException(status_code=400, detail="El email ya está registrado")

        # Crear nuevo usuario cliente con contraseña hasheada
        new_user = User(
            email=data.email,
            nombre=data.nombre,
            password_hash=hash_password(data.password),
            rol="cliente",
            tipo_usuario="cliente",
            taller_id=None  # Los clientes no tienen taller
        )
        print(f"🔄 Creando usuario cliente: email={new_user.email}")
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print(f"✅ Usuario cliente guardado: ID={new_user.id}, email={new_user.email}")

        # Crear cliente vinculado al usuario para que pueda hacer solicitudes
        cliente_id = str(uuid.uuid4())
        new_cliente = Cliente(
            id=cliente_id,
            nombre=data.nombre,
            telefono="",  # Se puede actualizar después
            email=data.email,
            foto=None,
            lat=0.0,
            lng=0.0,
            veces_atendido=0,
            calificacion_promedio=None
        )
        db.add(new_cliente)
        db.commit()
        print(f"✅ Cliente creado para usuario: ID={cliente_id}")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR en registro móvil: {type(e).__name__}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar usuario: {str(e)}")

    # Crear token JWT
    token = create_access_token(data={
        "sub": new_user.email,
        "nombre": new_user.nombre,
        "rol": new_user.rol,
        "taller_id": new_user.taller_id,
        "tipo_usuario": new_user.tipo_usuario
    })

    return RegisterResponse(
        success=True,
        token=token,
        message="Registro exitoso",
        user={
            "nombre": new_user.nombre,
            "email": new_user.email,
            "rol": new_user.rol,
            "tipo_usuario": new_user.tipo_usuario,
            "taller_id": new_user.taller_id
        }
    )


@router.post("/logout")
def logout():
    """Cerrar sesión (el frontend elimina el token)."""
    return {"success": True, "message": "Logout exitoso"}


@router.get("/me")
def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Obtener información del usuario actual desde el token JWT."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    # Verificar que el usuario existe en la base de datos
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    
    return {
        "email": user.email,
        "nombre": user.nombre,
        "rol": user.rol,
        "tipo_usuario": user.tipo_usuario,
        "taller_id": user.taller_id
    }


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    data: ChangePasswordRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Cambiar contraseña del usuario autenticado."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    # Buscar usuario
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    
    # Verificar contraseña actual
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    
    # Actualizar contraseña
    user.password_hash = hash_password(data.new_password)
    db.commit()
    
    return ChangePasswordResponse(
        success=True,
        message="Contraseña actualizada exitosamente"
    )
