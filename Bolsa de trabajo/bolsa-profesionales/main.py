from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sqlite3
import hashlib
import secrets
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

app = FastAPI(title="Bolsa de Profesionales UES - Verificación Real")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# ⚙️ CONFIGURACIÓN DEL SERVIDOR DE CORREO GMAIL (SMTP)
# Reemplaza con tu correo y la Contraseña de Aplicación de 16 caracteres
# ==============================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
GMAIL_USUARIO = "carreradetfytoues@gmail.com"        # <-- PON TU CORREO REAL AQUÍ
GMAIL_PASSWORD = "tvvjxgnpmtpdcqks"        # <-- PON TU CLAVE DE APLICACIÓN AQUÍ

def enviar_correo_verificacion(destinatario: str, codigo: str) -> bool:
    # Si aún no has puesto tu correo real, simula el código en consola
    if GMAIL_USUARIO == "tu_correo@gmail.com":
        print(f"\n📩 [MODO PRUEBA] Correo a: {destinatario} | Código de activación: {codigo}\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔑 Código de Activación UES: {codigo}"
        msg["From"] = f"Bolsa de Trabajo UES <{GMAIL_USUARIO}>"
        msg["To"] = destinatario

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 25px; background-color: #f8fafc; border-radius: 12px; max-width: 500px; margin: 0 auto; border: 1px solid #e2e8f0;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #4f46e5; margin: 0;">Universidad de El Salvador</h2>
                <p style="color: #64748b; font-size: 13px; margin-top: 5px;">Plataforma Oficial de Fisioterapia y Terapia Ocupacional</p>
            </div>
            <div style="background-color: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                <p style="color: #334155; font-size: 14px; margin-bottom: 15px;">Tu código de verificación para activar tu cuenta es:</p>
                <div style="font-size: 32px; font-weight: bold; color: #4f46e5; letter-spacing: 6px; padding: 10px; background-color: #e0e7ff; border-radius: 6px; display: inline-block;">
                    {codigo}
                </div>
                <p style="color: #64748b; font-size: 12px; margin-top: 15px;">Ingresa este código en la plataforma para completar tu registro.</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(GMAIL_USUARIO, GMAIL_PASSWORD.replace(" ", ""))
        server.sendmail(GMAIL_USUARIO, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Error al enviar correo por Gmail: {e}")
        return False

# ==============================================================================
# BASE DE DATOS Y TABLAS
# ==============================================================================
SESIONES_ACTIVAS = {}

def encriptar_password(password: str) -> str:
    salt = "UES_FISIOTERAPIA_2026"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def init_db():
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profesionales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            profesion TEXT NOT NULL,
            departamento TEXT NOT NULL,
            estudios TEXT,
            graduacion INTEGER NOT NULL,
            labora BOOLEAN NOT NULL,
            empresa TEXT,
            experiencia TEXT NOT NULL,
            telefono TEXT,
            correo TEXT,
            universidad TEXT DEFAULT 'Universidad de El Salvador',
            cambio_laboral BOOLEAN DEFAULT 0,
            es_verificado BOOLEAN DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            profesional_id INTEGER NOT NULL,
            es_admin BOOLEAN DEFAULT 0,
            esta_activado BOOLEAN DEFAULT 0,
            codigo_verificacion TEXT DEFAULT '',
            FOREIGN KEY(profesional_id) REFERENCES profesionales(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ofertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profesional_id INTEGER NOT NULL,
            empresa_nombre TEXT NOT NULL,
            empresa_contacto TEXT NOT NULL,
            titulo_plaza TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY(profesional_id) REFERENCES profesionales(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anuncios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            fecha TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # MIGRACIÓN SEGURA DE COLUMNAS
    cursor.execute("PRAGMA table_info(usuarios)")
    cols_u = [c[1] for c in cursor.fetchall()]
    if "esta_activado" not in cols_u:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN esta_activado BOOLEAN DEFAULT 0")
    if "codigo_verificacion" not in cols_u:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN codigo_verificacion TEXT DEFAULT ''")

    # CREACIÓN DEL ADMINISTRADOR MÁSTER
    cursor.execute("SELECT id FROM usuarios WHERE correo = 'adminfisioyto@ues.edu.sv'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO profesionales (nombre, profesion, departamento, universidad, estudios, graduacion, labora, empresa, cambio_laboral, experiencia, telefono, correo, es_verificado)
            VALUES ('Administrador General UES', 'Administrador de Sistema', 'San Salvador', 'Universidad de El Salvador', 'Gestor de Portal', 2026, 1, 'Universidad de El Salvador', 0, 'Cuenta con privilegios de supervisión.', '', 'adminfisioyto@ues.edu.sv', 1)
        """)
        admin_prof_id = cursor.lastrowid
        p_enc = encriptar_password("admin123")
        cursor.execute("""
            INSERT INTO usuarios (correo, password, profesional_id, es_admin, esta_activado, codigo_verificacion)
            VALUES ('adminfisioyto@ues.edu.sv', ?, ?, 1, 1, '')
        """, (p_enc, admin_prof_id))

    conn.commit()
    conn.close()

init_db()

# Modelos
class RegistroUsuario(BaseModel):
    correo: str
    password: str

class LoginUsuario(BaseModel):
    correo: str
    password: str

class ActivarCuenta(BaseModel):
    correo: str
    codigo: str

class ProfesionalUpdate(BaseModel):
    nombre: str
    profesion: str
    departamento: str
    universidad: str = "Universidad de El Salvador"
    estudios: Optional[str] = ""
    graduacion: int = Field(..., ge=1950, le=2030)
    labora: bool
    empresa: Optional[str] = ""
    cambio_laboral: bool = False
    experiencia: str
    telefono: Optional[str] = ""
    correo: Optional[str] = ""

class Profesional(ProfesionalUpdate):
    id: int
    es_verificado: bool = False

class OfertaCreate(BaseModel):
    profesional_id: int
    empresa_nombre: str
    empresa_contacto: str
    titulo_plaza: str
    mensaje: str

class AnuncioCreate(BaseModel):
    titulo: str
    mensaje: str

# --- AUTENTICACIÓN CON CÓDIGO DE VERIFICACIÓN ---
@app.post("/api/auth/registrar")
def registrar_usuario(u: RegistroUsuario):
    correo_limpio = u.correo.strip().lower()
    password_limpia = u.password.strip()
    
    if not correo_limpio or not password_limpia:
        raise HTTPException(status_code=400, detail="Los campos no pueden estar vacíos.")

    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, esta_activado FROM usuarios WHERE correo = ?", (correo_limpio,))
    existente = cursor.fetchone()
    
    if existente and existente[1] == 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Este correo ya está registrado y verificado.")
    
    codigo_6_digitos = str(random.randint(100000, 999999))
    p_encriptada = encriptar_password(password_limpia)

    try:
        if existente and existente[1] == 0:
            # Reintentar envío para un usuario pendiente
            cursor.execute("UPDATE usuarios SET password = ?, codigo_verificacion = ? WHERE correo = ?", 
                           (p_encriptada, codigo_6_digitos, correo_limpio))
        else:
            cursor.execute("""
                INSERT INTO profesionales (nombre, profesion, departamento, universidad, estudios, graduacion, labora, empresa, cambio_laboral, experiencia, telefono, correo, es_verificado)
                VALUES ('Nuevo Graduado', 'Licenciado en Fisioterapia', 'San Salvador', 'Universidad de El Salvador', '', 2026, 0, '', 0, 'Edita tu perfil...', '', ?, 0)
            """, (correo_limpio,))
            prof_id = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO usuarios (correo, password, profesional_id, es_admin, esta_activado, codigo_verificacion)
                VALUES (?, ?, ?, 0, 0, ?)
            """, (correo_limpio, p_encriptada, prof_id, codigo_6_digitos))

        conn.commit()
        conn.close()

        # Enviar el correo electrónico
        enviar_correo_verificacion(correo_limpio, codigo_6_digitos)
        return {"message": "Código de verificación enviado. Revisa tu bandeja de entrada o spam."}

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/activar")
def activar_cuenta(a: ActivarCuenta):
    correo_limpio = a.correo.strip().lower()
    codigo_limpio = a.codigo.strip()

    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE correo = ? AND codigo_verificacion = ?", (correo_limpio, codigo_limpio))
    user = cursor.fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=400, detail="Código de verificación incorrecto.")

    cursor.execute("UPDATE usuarios SET esta_activado = 1, codigo_verificacion = '' WHERE id = ?", (user[0],))
    conn.commit()
    conn.close()
    return {"message": "¡Cuenta verificada y activada con éxito! Ya puedes iniciar sesión."}

@app.post("/api/auth/login")
def login(u: LoginUsuario):
    correo_limpio = u.correo.strip().lower()
    password_limpia = u.password.strip()

    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    p_encriptada = encriptar_password(password_limpia)
    cursor.execute("SELECT profesional_id, es_admin, esta_activado FROM usuarios WHERE correo = ? AND password = ?", (correo_limpio, p_encriptada))
    resultado = cursor.fetchone()
    conn.close()
    
    if not resultado:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas.")
    
    prof_id, es_admin, esta_activado = resultado[0], bool(resultado[1]), bool(resultado[2])

    if not esta_activado:
        raise HTTPException(status_code=403, detail="Tu correo aún no está verificado. Ingresa el código enviado a tu cuenta.")

    token = secrets.token_hex(16)
    SESIONES_ACTIVAS[token] = {"prof_id": prof_id, "es_admin": es_admin}
    return {"token": token, "profesional_id": prof_id, "es_admin": es_admin}

# --- AUDITORÍA DE ADMINISTRADOR ---
@app.get("/api/admin/auditoria-ofertas")
def auditoria_ofertas(authorization: Optional[str] = Header(None)):
    if not authorization or authorization not in SESIONES_ACTIVAS or not SESIONES_ACTIVAS[authorization]["es_admin"]:
        raise HTTPException(status_code=403, detail="Acceso restringido a Administradores.")
        
    conn = sqlite3.connect("bolsa.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.profesional_id, p.nombre AS candidato_nombre, p.correo AS candidato_correo,
               o.empresa_nombre, o.empresa_contacto, o.titulo_plaza, o.mensaje, o.fecha
        FROM ofertas o
        JOIN profesionales p ON o.profesional_id = p.id
        ORDER BY o.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.put("/api/admin/profesionales/{prof_id}/verificar")
def toggle_verificacion(prof_id: int, authorization: Optional[str] = Header(None)):
    if not authorization or authorization not in SESIONES_ACTIVAS or not SESIONES_ACTIVAS[authorization]["es_admin"]:
        raise HTTPException(status_code=403, detail="No autorizado.")
        
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("SELECT es_verificado FROM profesionales WHERE id = ?", (prof_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")
        
    nuevo_estado = not bool(row[0])
    cursor.execute("UPDATE profesionales SET es_verificado = ? WHERE id = ?", (nuevo_estado, prof_id))
    conn.commit()
    conn.close()
    return {"message": "Estado de verificación actualizado.", "es_verificado": nuevo_estado}

@app.post("/api/admin/anuncios")
def crear_anuncio(a: AnuncioCreate, authorization: Optional[str] = Header(None)):
    if not authorization or authorization not in SESIONES_ACTIVAS or not SESIONES_ACTIVAS[authorization]["es_admin"]:
        raise HTTPException(status_code=403, detail="No autorizado.")
        
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO anuncios (titulo, mensaje) VALUES (?, ?)", (a.titulo, a.mensaje))
    conn.commit()
    conn.close()
    return {"message": "Anuncio publicado."}

@app.delete("/api/admin/anuncios/{anuncio_id}")
def borrar_anuncio(anuncio_id: int, authorization: Optional[str] = Header(None)):
    if not authorization or authorization not in SESIONES_ACTIVAS or not SESIONES_ACTIVAS[authorization]["es_admin"]:
        raise HTTPException(status_code=403, detail="No autorizado.")
        
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anuncios WHERE id = ?", (anuncio_id,))
    conn.commit()
    conn.close()
    return {"message": "Anuncio eliminado."}

@app.get("/api/anuncios")
def obtener_anuncios():
    conn = sqlite3.connect("bolsa.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM anuncios ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- OFERTAS Y DIRECTORIO ---
@app.post("/api/ofertas")
def enviar_oferta(o: OfertaCreate):
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ofertas (profesional_id, empresa_nombre, empresa_contacto, titulo_plaza, mensaje)
            VALUES (?, ?, ?, ?, ?)
        """, (o.profesional_id, o.empresa_nombre, o.empresa_contacto, o.titulo_plaza, o.mensaje))
        conn.commit()
        conn.close()
        return {"message": "Oferta enviada con éxito."}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ofertas/mis-ofertas")
def obtener_mis_ofertas(authorization: Optional[str] = Header(None)):
    if not authorization or authorization not in SESIONES_ACTIVAS:
        raise HTTPException(status_code=403, detail="No autorizado.")
        
    prof_id = SESIONES_ACTIVAS[authorization]["prof_id"]
    conn = sqlite3.connect("bolsa.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ofertas WHERE profesional_id = ? ORDER BY id DESC", (prof_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.delete("/api/ofertas/{oferta_id}")
def borrar_oferta(oferta_id: int, authorization: Optional[str] = Header(None)):
    if not authorization or authorization not in SESIONES_ACTIVAS:
        raise HTTPException(status_code=403, detail="No autorizado.")
        
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ofertas WHERE id = ?", (oferta_id,))
    conn.commit()
    conn.close()
    return {"message": "Oferta eliminada."}

@app.get("/api/profesionales", response_model=List[Profesional])
def obtener_profesionales():
    conn = sqlite3.connect("bolsa.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profesionales WHERE correo != 'adminfisioyto@ues.edu.sv' ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/profesionales/{prof_id}", response_model=Profesional)
def obtener_un_profesional(prof_id: int):
    conn = sqlite3.connect("bolsa.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profesionales WHERE id = ?", (prof_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return dict(row)

@app.put("/api/profesionales/{prof_id}")
def actualizar_perfil(prof_id: int, prof: ProfesionalUpdate, authorization: Optional[str] = Header(None)):
    if not authorization or authorization not in SESIONES_ACTIVAS or SESIONES_ACTIVAS[authorization]["prof_id"] != prof_id:
        raise HTTPException(status_code=403, detail="No autorizado.")
        
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE profesionales 
            SET nombre=?, profesion=?, departamento=?, universidad=?, estudios=?, graduacion=?, labora=?, empresa=?, cambio_laboral=?, experiencia=?, telefono=?, correo=?
            WHERE id = ?
        """, (prof.nombre, prof.profesion, prof.departamento, prof.universidad, prof.estudios, prof.graduacion, prof.labora, prof.empresa, prof.cambio_laboral, prof.experiencia, prof.telefono, prof.correo, prof_id))
        conn.commit()
        conn.close()
        return {"message": "Perfil actualizado."}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/profesionales/{prof_id}")
def eliminar_perfil(prof_id: int, authorization: Optional[str] = Header(None)):
    sess = SESIONES_ACTIVAS.get(authorization)
    if not sess or (sess["prof_id"] != prof_id and not sess["es_admin"]):
        raise HTTPException(status_code=403, detail="No autorizado.")
        
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM usuarios WHERE profesional_id = ?", (prof_id,))
        cursor.execute("DELETE FROM profesionales WHERE id = ?", (prof_id,))
        cursor.execute("DELETE FROM ofertas WHERE profesional_id = ?", (prof_id,))
        conn.commit()
        conn.close()
        return {"message": "Perfil eliminado."}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))