import hashlib
import os
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

# ----------------------------------------------------
# CONFIGURACIÓN DE BASE DE DATOS
# ----------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    ),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ----------------------------------------------------
# MODELOS DE BASE DE DATOS (SQLAlchemy)
# ----------------------------------------------------
class UsuarioDB(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    correo = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    codigo_activacion = Column(String, nullable=True)  # Se mantiene nulo
    verificado = Column(Boolean, default=True)  # Verificado por defecto
    es_admin = Column(Boolean, default=False)

    profesional = relationship(
        "ProfesionalDB", back_populates="usuario", uselist=False
    )


class ProfesionalDB(Base):
    __tablename__ = "profesionales"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    correo = Column(String)
    nombre_completo = Column(String, nullable=True)
    titulo_academico = Column(String, nullable=True)
    universidad = Column(String, nullable=True)
    departamento = Column(String, nullable=True)
    disponibilidad = Column(String, nullable=True)
    ano_graduacion = Column(Integer, nullable=True)
    experiencia = Column(Text, nullable=True)
    lugar_trabajo = Column(String, nullable=True)

    usuario = relationship("UsuarioDB", back_populates="profesional")


Base.metadata.create_all(bind=engine)


# ----------------------------------------------------
# ESQUEMAS DE ENTRADA (Pydantic)
# ----------------------------------------------------
class RegistroAuth(BaseModel):
    correo: str
    password: str


class LoginAuth(BaseModel):
    correo: str
    password: str


class PerfilUpdate(BaseModel):
    nombre_completo: Optional[str] = None
    titulo_academico: Optional[str] = None
    universidad: Optional[str] = None
    departamento: Optional[str] = None
    disponibilidad: Optional[str] = None
    ano_graduacion: Optional[int] = None
    experiencia: Optional[str] = None
    lugar_trabajo: Optional[str] = None


# ----------------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------------
def hash_password(password: str) -> str:
    """Genera un hash SHA256 para la contraseña."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ----------------------------------------------------
# INICIALIZACIÓN DE FASTAPI Y CORS
# ----------------------------------------------------
app = FastAPI(title="Sistema de Datos y Directorio Profesional")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------
# ENDPOINTS DE AUTENTICACIÓN
# ----------------------------------------------------
@app.get("/")
def inicio():
    return {"status": "ok", "mensaje": "API de Seguimiento Profesional activa"}


@app.post("/api/auth/registrar")
def registrar(datos: RegistroAuth):
    db = SessionLocal()
    try:
        correo_norm = datos.correo.strip().lower()
        pass_norm = datos.password.strip()
        pwd_h = hash_password(pass_norm)

        user_exist = (
            db.query(UsuarioDB).filter(UsuarioDB.correo == correo_norm).first()
        )

        es_admin_user = correo_norm == "carreradetfytoues@gmail.com" or (
            correo_norm.endswith("@ues.edu.sv") and "admin" in correo_norm
        )

        # Si el usuario ya existe, le actualizamos la contraseña automáticamente
        if user_exist:
            user_exist.password_hash = pwd_h
            user_exist.verificado = True
            user_exist.codigo_activacion = None
            user_exist.es_admin = es_admin_user
            db.commit()
            return {
                "status": "ok",
                "mensaje": "¡Contraseña actualizada con éxito! Ya puedes iniciar sesión.",
            }

        # Si es un usuario nuevo, lo creamos directamente verificado y sin código
        nuevo_usuario = UsuarioDB(
            correo=correo_norm,
            password_hash=pwd_h,
            codigo_activacion=None,
            verificado=True,
            es_admin=es_admin_user,
        )
        db.add(nuevo_usuario)
        db.commit()

        # Creamos la ficha de profesional en blanco ligada al nuevo usuario
        nuevo_prof = ProfesionalDB(
            usuario_id=nuevo_usuario.id, correo=correo_norm
        )
        db.add(nuevo_prof)
        db.commit()

        return {
            "status": "ok",
            "mensaje": "¡Cuenta creada con éxito! Ya puedes iniciar sesión.",
        }
    finally:
        db.close()


@app.post("/api/auth/login")
def login(datos: LoginAuth):
    db = SessionLocal()
    try:
        correo_norm = datos.correo.strip().lower()
        pass_norm = datos.password.strip()
        pwd_h = hash_password(pass_norm)

        usuario = (
            db.query(UsuarioDB)
            .filter(
                UsuarioDB.correo == correo_norm,
                UsuarioDB.password_hash == pwd_h,
            )
            .first()
        )

        if not usuario:
            raise HTTPException(
                status_code=400, detail="Correo o contraseña incorrectos."
            )

        return {
            "status": "ok",
            "mensaje": "Inicio de sesión exitoso.",
            "usuario": {
                "id": usuario.id,
                "correo": usuario.correo,
                "es_admin": usuario.es_admin,
            },
        }
    finally:
        db.close()


# ----------------------------------------------------
# ENDPOINTS DEL DIRECTORIO Y PERFIL
# ----------------------------------------------------
@app.get("/api/profesionales")
def obtener_profesionales():
    db = SessionLocal()
    try:
        profesionales = db.query(ProfesionalDB).all()
        resultado = []
        for p in profesionales:
            resultado.append(
                {
                    "id": p.id,
                    "usuario_id": p.usuario_id,
                    "correo": p.correo,
                    "nombre_completo": p.nombre_completo
                    or "Nombre no registrado",
                    "titulo_academico": p.titulo_academico
                    or "Licenciado en Fisioterapia y Terapia Ocupacional",
                    "universidad": p.universidad or "Universidad de El Salvador",
                    "departamento": p.departamento or "San Salvador",
                    "disponibilidad": p.disponibilidad
                    or "Laborando actualmente",
                    "ano_graduacion": p.ano_graduacion or 2023,
                    "experiencia": p.experiencia or "Sin información agregada.",
                    "lugar_trabajo": p.lugar_trabajo
                    or "Universidad de El Salvador",
                }
            )
        return resultado
    finally:
        db.close()


@app.put("/api/profesionales/{usuario_id}")
def actualizar_perfil(usuario_id: int, perfil: PerfilUpdate):
    db = SessionLocal()
    try:
        prof = (
            db.query(ProfesionalDB)
            .filter(ProfesionalDB.usuario_id == usuario_id)
            .first()
        )
        if not prof:
            raise HTTPException(
                status_code=404, detail="Perfil profesional no encontrado."
            )

        if perfil.nombre_completo is not None:
            prof.nombre_completo = perfil.nombre_completo
        if perfil.titulo_academico is not None:
            prof.titulo_academico = perfil.titulo_academico
        if perfil.universidad is not None:
            prof.universidad = perfil.universidad
        if perfil.departamento is not None:
            prof.departamento = perfil.departamento
        if perfil.disponibilidad is not None:
            prof.disponibilidad = perfil.disponibilidad
        if perfil.ano_graduacion is not None:
            prof.ano_graduacion = perfil.ano_graduacion
        if perfil.experiencia is not None:
            prof.experiencia = perfil.experiencia
        if perfil.lugar_trabajo is not None:
            prof.lugar_trabajo = perfil.lugar_trabajo

        db.commit()
        return {
            "status": "ok",
            "mensaje": "Perfil profesional actualizado correctamente.",
        }
    finally:
        db.close()