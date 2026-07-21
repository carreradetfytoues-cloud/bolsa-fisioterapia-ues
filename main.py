import hashlib
import os
import random
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

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

# 2. CONFIGURACIÓN DE CORREO SMTP (GMAIL)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "carreradetfytoues@gmail.com")
SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD", ""
)  # Contraseña de Aplicación de Gmail


def enviar_correo_activacion(correo_destino: str, codigo: str):
    """Envía el código de 6 dígitos por correo usando Gmail SMTP"""
    if not SMTP_PASSWORD:
        print(f"⚠️ SMTP_PASSWORD no configurada. Código para {correo_destino}: {codigo}")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Código de Activación UES: {codigo}"
        msg["From"] = f"Bolsa de Trabajo UES <{SMTP_USER}>"
        msg["To"] = correo_destino

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #1e293b; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px;">
                <h2 style="color: #4f46e5; margin-bottom: 8px;">Universidad de El Salvador</h2>
                <p style="color: #64748b; font-size: 14px; margin-top: 0;">Plataforma Oficial de Fisioterapia y Terapia Ocupacional</p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                <p style="font-size: 15px;">Tu código de verificación para activar tu cuenta es:</p>
                <div style="background: #f1f5f9; text-align: center; padding: 16px; border-radius: 8px; font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #4f46e5; margin: 20px 0;">
                    {codigo}
                </div>
                <p style="font-size: 13px; color: #94a3b8;">Ingresa este código en la plataforma para completar tu registro.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, correo_destino, msg.as_string())
        server.close()
        print(f"✅ Correo enviado exitosamente a {correo_destino}")
    except Exception as e:
        print(f"❌ Error enviando correo SMTP: {e}")


# 3. MODELOS SQLALCHEMY
class UsuarioDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    correo = Column(String, unique=True, index=True)
    password_hash = Column(String)
    codigo_activacion = Column(String)
    verificado = Column(Boolean, default=False)
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

# 4. APP FASTAPI
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


# 5. RUTAS DE AUTENTICACIÓN
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

        # Generar código dinámico aleatorio de 6 dígitos
        codigo_nuevo = str(random.randint(100000, 999999))
        pwd_h = hash_password(datos.password)

        nuevo_usuario = UsuarioDB(
            correo=datos.correo,
            password_hash=pwd_h,
            codigo_activacion=codigo_nuevo,
            verificado=False,
        )
        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)

        nuevo_prof = ProfesionalDB(
            usuario_id=nuevo_usuario.id, correo=datos.correo
        )
        db.add(nuevo_prof)
        db.commit()

        # Enviar correo real
        enviar_correo_activacion(datos.correo, codigo_nuevo)

        return {
            "status": "ok",
            "mensaje": "Usuario registrado. Revisa tu correo electrónico para obtener el código.",
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

        if user.codigo_activacion != datos.codigo:
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
        }
    finally:
        db.close()


# 6. RUTAS DE DIRECTORIO
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


@app.get("/api/profesionales")
def listar_profesionales():
    db = SessionLocal()
    try:
        return db.query(ProfesionalDB).all()
    finally:
        db.close()