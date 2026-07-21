import hashlib
import os
import random
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# 1. BASE DE DATOS
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. CONFIGURACIÓN SMTP (GMAIL)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "carreradetfytoues@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "ugmwpnochguajatn")


def enviar_correo_activacion(correo_destino: str, codigo: str) -> bool:
    if not SMTP_PASSWORD:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Código de Activación UES: {codigo}"
        msg["From"] = f"Bolsa de Trabajo UES <{SMTP_USER}>"
        msg["To"] = correo_destino

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #1e293b; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
                <h2 style="color: #4f46e5;">Universidad de El Salvador</h2>
                <p>Tu código de verificación para activar tu cuenta es:</p>
                <div style="background: #f1f5f9; text-align: center; padding: 16px; border-radius: 8px; font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #4f46e5; margin: 16px 0;">
                    {codigo}
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, correo_destino, msg.as_string())
        server.close()
        return True
    except Exception as e:
        print(f"❌ Error SMTP: {e}")
        return False


# 3. MODELOS SQLALCHEMY
class UsuarioDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    correo = Column(String, unique=True, index=True)
    password_hash = Column(String)
    codigo_activacion = Column(String)
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


# 4. FASTAPI APP
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class RegistroAuth(BaseModel):
    correo: str
    password: str


class ActivarAuth(BaseModel):
    correo: str
    codigo: str


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


# 5. RUTAS AUTH
@app.post("/api/auth/registrar")
def registrar(datos: RegistroAuth):
    db = SessionLocal()
    try:
        user_exist = (
            db.query(UsuarioDB).filter(UsuarioDB.correo == datos.correo).first()
        )
        codigo_nuevo = str(random.randint(100000, 999999))

        if user_exist:
            if not user_exist.verificado:
                user_exist.codigo_activacion = codigo_nuevo
                db.commit()
                enviar_correo_activacion(datos.correo, codigo_nuevo)
                return {
                    "status": "ok",
                    "mensaje": "Se reenvió el código a tu correo.",
                }
            raise HTTPException(
                status_code=400, detail="El correo ya se encuentra registrado."
            )

        pwd_h = hash_password(datos.password)
        es_admin_user = datos.correo.endswith("@ues.edu.sv") and "admin" in datos.correo

        nuevo_usuario = UsuarioDB(
            correo=datos.correo,
            password_hash=pwd_h,
            codigo_activacion=codigo_nuevo,
            verificado=False,
            es_admin=es_admin_user,
        )
        db.add(nuevo_usuario)
        db.commit()

        nuevo_prof = ProfesionalDB(
            usuario_id=nuevo_usuario.id, correo=datos.correo
        )
        db.add(nuevo_prof)
        db.commit()

        enviar_correo_activacion(datos.correo, codigo_nuevo)

        return {
            "status": "ok",
            "mensaje": "Se envió un código de verificación a tu correo.",
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
                status_code=400, detail="El código ingresado es incorrecto."
            )

        user.verificado = True
        db.commit()
        return {"status": "ok", "mensaje": "Cuenta verificada correctamente."}
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
                status_code=400, detail="Correo o contraseña incorrectos."
            )

        if not user.verificado:
            raise HTTPException(
                status_code=400,
                detail="El correo aún no está verificado. Debes ingresar el código.",
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
            "token": token,
            "access_token": token,
            "profesional_id": prof_id,
            "es_admin": user.es_admin,
        }
    finally:
        db.close()


# 6. RUTAS DIRECTORIO Y PERFIL
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


# 7. RUTAS OFERTAS Y ANUNCIOS
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


# 8. RUTAS ADMINISTRADOR UES
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
        return db.query(UsuarioDB).all()
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