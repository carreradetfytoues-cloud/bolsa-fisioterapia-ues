import hashlib
import os
import secrets
from typing import List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# 1. CONFIGURACIÓN DE BASE DE DATOS (NEON POSTGRESQL / SQLITE LOCAL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 2. MODELOS DE TABLAS
class UsuarioDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    correo = Column(String, unique=True, index=True)
    password_hash = Column(String)
    codigo_activacion = Column(String, default="123456")
    verificado = Column(Boolean, default=False)
    es_admin = Column(Boolean, default=False)
    token = Column(String, nullable=True)

    profesional = relationship(
        "ProfesionalDB", back_populates="usuario", uselist=False
    )


class ProfesionalDB(Base):
    __tablename__ = "profesionales"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    nombre = Column(String, default="")
    universidad = Column(String, default="")
    profesion = Column(String, default="")
    carrera = Column(String, default="")
    departamento = Column(String, default="")
    contacto = Column(String, default="")
    telefono = Column(String, default="")
    correo = Column(String, default="")
    estudios = Column(String, default="")
    graduacion = Column(Integer, nullable=True)
    anio_graduacion = Column(Integer, nullable=True)
    labora = Column(Boolean, default=False)
    empresa = Column(String, default="")
    cambio_laboral = Column(Boolean, default=False)
    experiencia = Column(String, default="")

    usuario = relationship("UsuarioDB", back_populates="profesional")


Base.metadata.create_all(bind=engine)

# 3. FASTAPI Y MIDDLEWARE CORS
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# FUNCIONES AUXILIARES
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# 4. ESQUEMAS DE ENTRADA (PYDANTIC)
class RegistroAuth(BaseModel):
    correo: str
    password: str


class ActivarAuth(BaseModel):
    correo: str
    codigo: str


class ProfesionalEsquema(BaseModel):
    nombre: Optional[str] = ""
    universidad: Optional[str] = ""
    profesion: Optional[str] = ""
    carrera: Optional[str] = ""
    departamento: Optional[str] = ""
    contacto: Optional[str] = ""
    telefono: Optional[str] = ""
    correo: Optional[str] = ""
    estudios: Optional[str] = ""
    graduacion: Optional[int] = None
    anio_graduacion: Optional[int] = None
    labora: Optional[bool] = False
    empresa: Optional[str] = ""
    cambio_laboral: Optional[bool] = False
    experiencia: Optional[str] = ""


# 5. RUTAS DE AUTENTICACIÓN (AUTH)
@app.post("/api/auth/registrar")
def registrar(datos: RegistroAuth):
    db = SessionLocal()
    try:
        user_exist = (
            db.query(UsuarioDB).filter(UsuarioDB.correo == datos.correo).first()
        )
        if user_exist:
            raise HTTPException(
                status_code=400, detail="El correo ya se encuentra registrado."
            )

        pwd_h = hash_password(datos.password)
        codigo_demo = "123456"  # Código por defecto para pruebas
        nuevo_usuario = UsuarioDB(
            correo=datos.correo,
            password_hash=pwd_h,
            codigo_activacion=codigo_demo,
            verificado=False,
        )
        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)

        # Crear perfil profesional vacío asociado a la cuenta
        nuevo_prof = ProfesionalDB(
            usuario_id=nuevo_usuario.id, correo=datos.correo
        )
        db.add(nuevo_prof)
        db.commit()

        return {
            "status": "ok",
            "mensaje": "Usuario registrado. Usa el código 123456 para activar tu cuenta.",
        }
    finally:
        db.close()


@app.post("/api/auth/activar")
def activar(datos: ActivarAuth):
    db = SessionLocal()
    try:
        user = db.query(UsuarioDB).filter(UsuarioDB.correo == datos.correo).first()
        if not user:
            raise HTTPException(
                status_code=400, detail="Usuario no encontrado."
            )

        if user.codigo_activacion != datos.codigo and datos.codigo != "123456":
            raise HTTPException(
                status_code=400, detail="Código de activación incorrecto."
            )

        user.verificado = True
        db.commit()
        return {"status": "ok", "mensaje": "Cuenta activada correctamente."}
    finally:
        db.close()


@app.post("/api/auth/login")
def login(datos: RegistroAuth):
    db = SessionLocal()
    try:
        pwd_h = hash_password(datos.password)
        user = (
            db.query(UsuarioDB)
            .filter(
                UsuarioDB.correo == datos.correo,
                UsuarioDB.password_hash == pwd_h,
            )
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=400, detail="Credenciales incorrectas."
            )

        if not user.verificado:
            raise HTTPException(
                status_code=400, detail="El correo aún no está verificado."
            )

        token = secrets.token_hex(16)
        user.token = token
        db.commit()

        prof = (
            db.query(ProfesionalDB)
            .filter(ProfesionalDB.usuario_id == user.id)
            .first()
        )
        prof_id = prof.id if prof else None

        return {
            "access_token": token,
            "token": token,
            "profesional_id": prof_id,
            "es_admin": user.es_admin,
        }
    finally:
        db.close()


# 6. RUTAS DE PERFIL Y DIRECTORIO
@app.get("/api/profesionales/me")
def obtener_mi_perfil(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado.")
    token = authorization.split(" ")[1]
    db = SessionLocal()
    try:
        user = db.query(UsuarioDB).filter(UsuarioDB.token == token).first()
        if not user:
            raise HTTPException(status_code=401, detail="No autorizado.")

        prof = (
            db.query(ProfesionalDB)
            .filter(ProfesionalDB.usuario_id == user.id)
            .first()
        )
        if not prof:
            prof = ProfesionalDB(usuario_id=user.id, correo=user.correo)
            db.add(prof)
            db.commit()
            db.refresh(prof)
        return prof
    finally:
        db.close()


@app.put("/api/profesionales/{prof_id}")
def actualizar_profesional(
    prof_id: int,
    datos: ProfesionalEsquema,
    authorization: Optional[str] = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado.")
    token = authorization.split(" ")[1]
    db = SessionLocal()
    try:
        user = db.query(UsuarioDB).filter(UsuarioDB.token == token).first()
        if not user:
            raise HTTPException(status_code=401, detail="No autorizado.")

        prof = (
            db.query(ProfesionalDB).filter(ProfesionalDB.id == prof_id).first()
        )
        if not prof:
            raise HTTPException(
                status_code=404, detail="Perfil no encontrado."
            )

        for key, value in datos.dict().items():
            if value is not None and hasattr(prof, key):
                setattr(prof, key, value)

        db.commit()
        db.refresh(prof)
        return prof
    finally:
        db.close()


@app.post("/api/profesionales")
def crear_profesional(datos: ProfesionalEsquema):
    db = SessionLocal()
    try:
        nuevo = ProfesionalDB(**datos.dict())
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo
    finally:
        db.close()


@app.get("/api/profesionales")
def listar_profesionales():
    db = SessionLocal()
    try:
        return db.query(ProfesionalDB).all()
    finally:
        db.close()