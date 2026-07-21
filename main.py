import hashlib
import os
import secrets
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# --------------------------------------------------------------------
# 1. BASE DE DATOS
# --------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --------------------------------------------------------------------
# 2. MODELOS SQLALCHEMY (TODAS LAS TABLAS RESTAURADAS)
# --------------------------------------------------------------------
class UsuarioDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    correo = Column(String, unique=True, index=True)
    password_hash = Column(String)
    codigo_activacion = Column(String, nullable=True)  # Queda deshabilitado / nulo
    verificado = Column(Boolean, default=True)         # Verificado por defecto
    es_admin = Column(Boolean, default=False)
    token = Column(String, nullable=True)

    profesional = relationship("ProfesionalDB", back_populates="usuario", uselist=False)


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
    verificado_ues = Column(Boolean, default=False)

    usuario = relationship("UsuarioDB", back_populates="profesional")
    ofertas = relationship("OfertaDB", back_populates="profesional")


class OfertaDB(Base):
    __tablename__ = "ofertas"
    id = Column(Integer, primary_key=True, index=True)
    profesional_id = Column(Integer, ForeignKey("profesionales.id"))
    empresa = Column(String)
    contacto = Column(String)
    vacante = Column(String)
    mensaje = Column(String)

    profesional = relationship("ProfesionalDB", back_populates="ofertas")


class AnuncioDB(Base):
    __tablename__ = "anuncios"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String)
    mensaje = Column(String)


Base.metadata.create_all(bind=engine)


def es_registro_completo(p: ProfesionalDB) -> bool:
    return bool(
        p.nombre
        and p.nombre.strip() != ""
        and p.experiencia
        and p.experiencia.strip() != ""
    )


# --------------------------------------------------------------------
# 3. FASTAPI APP Y ESQUEMAS PYDANTIC
# --------------------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode()).hexdigest()


class RegistroAuth(BaseModel):
    correo: str
    password: str


class OfertaEsquema(BaseModel):
    profesional_id: int
    empresa: str
    contacto: str
    vacante: str
    mensaje: str


class AnuncioEsquema(BaseModel):
    titulo: str
    mensaje: str


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


# --------------------------------------------------------------------
# 4. RUTAS DE AUTENTICACIÓN
# --------------------------------------------------------------------
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

        es_admin_user = (
            correo_norm == "carreradetfytoues@gmail.com"
            or (correo_norm.endswith("@ues.edu.sv") and "admin" in correo_norm)
        )

        # Si el usuario ya existe, le actualizamos la contraseña
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

        # Si es usuario nuevo, lo creamos directamente verificado sin códigos
        nuevo_usuario = UsuarioDB(
            correo=correo_norm,
            password_hash=pwd_h,
            codigo_activacion=None,
            verificado=True,
            es_admin=es_admin_user,
        )
        db.add(nuevo_usuario)
        db.commit()

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
def login(datos: RegistroAuth):
    db = SessionLocal()
    try:
        correo_norm = datos.correo.strip().lower()
        pass_norm = datos.password.strip()
        pwd_h = hash_password(pass_norm)

        user = (
            db.query(UsuarioDB)
            .filter(
                UsuarioDB.correo == correo_norm,
                UsuarioDB.password_hash == pwd_h,
            )
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=400, detail="Correo o contraseña incorrectos."
            )

        if correo_norm == "carreradetfytoues@gmail.com":
            user.es_admin = True

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
            "token": token,
            "access_token": token,
            "profesional_id": prof_id,
            "es_admin": user.es_admin,
        }
    finally:
        db.close()


# --------------------------------------------------------------------
# 5. RUTAS DE DIRECTORIO Y PERFIL
# --------------------------------------------------------------------
@app.get("/api/profesionales")
def listar_profesionales():
    db = SessionLocal()
    try:
        todos = db.query(ProfesionalDB).all()
        return [p for p in todos if es_registro_completo(p)]
    finally:
        db.close()


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
        return prof
    finally:
        db.close()


@app.put("/api/profesionales/me")
@app.post("/api/profesionales/me")
@app.post("/api/profesionales")
def actualizar_mi_perfil(
    datos: ProfesionalEsquema, authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Sesión expirada. Inicia sesión nuevamente.",
        )
    token = authorization.split(" ")[1]
    db = SessionLocal()
    try:
        user = db.query(UsuarioDB).filter(UsuarioDB.token == token).first()
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Sesión expirada. Inicia sesión nuevamente.",
            )

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

        for key, value in datos.dict().items():
            if value is not None and hasattr(prof, key):
                setattr(prof, key, value)

        db.commit()
        db.refresh(prof)
        return prof
    finally:
        db.close()


@app.put("/api/profesionales/{prof_id}")
def actualizar_profesional_por_id(
    prof_id: int,
    datos: ProfesionalEsquema,
    authorization: Optional[str] = Header(None),
):
    return actualizar_mi_perfil(datos, authorization)


@app.delete("/api/profesionales/me")
def eliminar_mi_cuenta(authorization: Optional[str] = Header(None)):
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
        if prof:
            db.query(OfertaDB).filter(
                OfertaDB.profesional_id == prof.id
            ).delete()
            db.delete(prof)

        db.delete(user)
        db.commit()
        return {"status": "ok", "mensaje": "Cuenta eliminada."}
    finally:
        db.close()


# --------------------------------------------------------------------
# 6. RUTAS DE OFERTAS Y ANUNCIOS
# --------------------------------------------------------------------
@app.post("/api/ofertas")
def crear_oferta(datos: OfertaEsquema):
    db = SessionLocal()
    try:
        nueva_oferta = OfertaDB(
            profesional_id=datos.profesional_id,
            empresa=datos.empresa,
            contacto=datos.contacto,
            vacante=datos.vacante,
            mensaje=datos.mensaje,
        )
        db.add(nueva_oferta)
        db.commit()
        return {"status": "ok", "mensaje": "Oferta enviada."}
    finally:
        db.close()


@app.get("/api/ofertas/me")
def mis_ofertas(authorization: Optional[str] = Header(None)):
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
            return []

        return (
            db.query(OfertaDB).filter(OfertaDB.profesional_id == prof.id).all()
        )
    finally:
        db.close()


@app.get("/api/anuncios")
def listar_anuncios():
    db = SessionLocal()
    try:
        return db.query(AnuncioDB).all()
    finally:
        db.close()


# --------------------------------------------------------------------
# 7. RUTAS ADMINISTRADOR UES
# --------------------------------------------------------------------
@app.get("/api/admin/ofertas")
def admin_listar_ofertas(authorization: Optional[str] = Header(None)):
    db = SessionLocal()
    try:
        ofertas = db.query(OfertaDB).all()
        res = []
        for o in ofertas:
            prof = (
                db.query(ProfesionalDB)
                .filter(ProfesionalDB.id == o.profesional_id)
                .first()
            )
            res.append(
                {
                    "empresa": o.empresa,
                    "candidato_nombre": prof.nombre if prof else "N/A",
                    "vacante": o.vacante,
                    "mensaje": o.mensaje,
                    "contacto": o.contacto,
                }
            )
        return res
    finally:
        db.close()


@app.post("/api/admin/anuncios")
def admin_crear_anuncio(
    datos: AnuncioEsquema, authorization: Optional[str] = Header(None)
):
    db = SessionLocal()
    try:
        nuevo = AnuncioDB(titulo=datos.titulo, mensaje=datos.mensaje)
        db.add(nuevo)
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()


@app.get("/api/admin/usuarios")
def admin_listar_usuarios(authorization: Optional[str] = Header(None)):
    db = SessionLocal()
    try:
        usuarios = db.query(UsuarioDB).all()
        res = []
        for u in usuarios:
            prof = (
                db.query(ProfesionalDB)
                .filter(ProfesionalDB.usuario_id == u.id)
                .first()
            )
            res.append(
                {
                    "id": u.id,
                    "correo": u.correo,
                    "verificado": u.verificado,
                    "es_admin": u.es_admin,
                    "verificado_ues": prof.verificado_ues if prof else False,
                }
            )
        return res
    finally:
        db.close()


@app.put("/api/admin/usuarios/{user_id}/verificar")
def admin_toggle_verificar(
    user_id: int, authorization: Optional[str] = Header(None)
):
    db = SessionLocal()
    try:
        prof = (
            db.query(ProfesionalDB)
            .filter(ProfesionalDB.usuario_id == user_id)
            .first()
        )
        if not prof:
            raise HTTPException(
                status_code=404, detail="Perfil profesional no encontrado."
            )

        prof.verificado_ues = not prof.verificado_ues
        db.commit()
        return {"status": "ok", "verificado_ues": prof.verificado_ues}
    finally:
        db.close()


@app.delete("/api/admin/usuarios/{user_id}")
def admin_eliminar_usuario(
    user_id: int, authorization: Optional[str] = Header(None)
):
    db = SessionLocal()
    try:
        user = db.query(UsuarioDB).filter(UsuarioDB.id == user_id).first()
        if user:
            prof = (
                db.query(ProfesionalDB)
                .filter(ProfesionalDB.usuario_id == user.id)
                .first()
            )
            if prof:
                db.query(OfertaDB).filter(
                    OfertaDB.profesional_id == prof.id
                ).delete()
                db.delete(prof)
            db.delete(user)
            db.commit()
        return {"status": "ok"}
    finally:
        db.close()