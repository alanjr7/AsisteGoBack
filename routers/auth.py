from fastapi import APIRouter, HTTPException, Header, Depends
from sqlalchemy.orm import Session
import uuid
from models import (
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse,
    ChangePasswordRequest, ChangePasswordResponse
)
from database_sql import get_db, User, Cliente
from database import db as memory_db
from utils.security import (
    hash_password, verify_password, create_access_token, decode_access_token
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Autenticar usuario y retornar token JWT."""
    # Buscar usuario en MySQL
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    # Crear token JWT
    token = create_access_token(data={"sub": user.email, "nombre": user.nombre, "rol": user.rol})
    
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

        # Crear nuevo usuario con contraseña hasheada
        new_user = User(
            email=data.email,
            nombre=data.nombre,
            password_hash=hash_password(data.password),
            rol="encargado"
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

    # Crear token JWT
    token = create_access_token(data={"sub": new_user.email, "nombre": new_user.nombre, "rol": new_user.rol})

    return RegisterResponse(
        success=True,
        token=token,
        message="Registro exitoso",
        user={
            "nombre": new_user.nombre,
            "email": new_user.email,
            "rol": new_user.rol
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
        "rol": user.rol
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
