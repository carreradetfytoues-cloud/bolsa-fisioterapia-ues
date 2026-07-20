import os
import zipfile

PROJECT_DIR = "bolsa-profesionales"

def main():
    print("=" * 60)
    print("      CONFIGURADOR DE ENTORNO LOCAL - TALENTPOOL v1.1")
    print("=" * 60)
    
    # 1. Crear directorio del proyecto
    if not os.path.exists(PROJECT_DIR):
        os.makedirs(PROJECT_DIR)
        print(f" [+] Carpeta creada: '{PROJECT_DIR}'")
    else:
        print(f" [!] La carpeta '{PROJECT_DIR}' ya existe. Sobrescribiendo archivos...")

    # 2. Generar requirements.txt
    req_content = "fastapi==0.110.0\nuvicorn==0.28.0\n"
    with open(os.path.join(PROJECT_DIR, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(req_content)
    print(" [+] Archivo generado exitosamente: requirements.txt")

    # 3. Generar main.py (FastAPI Backend)
    main_content = '''from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sqlite3
from typing import List, Optional

app = FastAPI(title="Bolsa de Profesionales API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profesionales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            profesion TEXT NOT NULL,
            estudios TEXT,
            graduacion INTEGER NOT NULL,
            labora BOOLEAN NOT NULL,
            empresa TEXT,
            experiencia TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

class ProfesionalCreate(BaseModel):
    nombre: str
    profesion: str
    estudios: Optional[str] = ""
    graduacion: int = Field(..., ge=1950, le=2030)
    labora: bool
    empresa: Optional[str] = ""
    experiencia: str

class Profesional(ProfesionalCreate):
    id: int

@app.post("/api/profesionales", response_model=Profesional, status_code=201)
def crear_profesional(prof: ProfesionalCreate):
    conn = sqlite3.connect("bolsa.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO profesionales (nombre, profesion, estudios, graduacion, labora, empresa, experiencia)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (prof.nombre, prof.profesion, prof.estudios, prof.graduacion, prof.labora, prof.empresa, prof.experiencia))
        conn.commit()
        nuevo_id = cursor.lastrowid
        conn.close()
        return {**prof.model_dump(), "id": nuevo_id}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {str(e)}")

@app.get("/api/profesionales", response_model=List[Profesional])
def obtener_profesionales():
    conn = sqlite3.connect("bolsa.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profesionales ORDER BY graduacion DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
'''
    with open(os.path.join(PROJECT_DIR, "main.py"), "w", encoding="utf-8") as f:
        f.write(main_content)
    print(" [+] Archivo generado exitosamente: main.py")

    # 4. Generar index.html (Tailwind HTML Frontend)
    html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bolsa de Profesionales Inteligente</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght=300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen">

    <header class="bg-indigo-600 text-white shadow-md">
        <div class="container mx-auto px-6 py-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold tracking-tight">TalentPool <span class="text-indigo-200 text-sm font-normal">v1.0</span></h1>
            <span class="bg-indigo-800 text-xs px-3 py-1 rounded-full">Sistemas & IA</span>
        </div>
    </header>

    <main class="container mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <section class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 h-fit">
            <h2 class="text-xl font-bold mb-4 text-gray-900">Registrar Profesional</h2>
            <form id="professionalForm" class="space-y-4">
                <div>
                    <label class="block text-sm font-semibold text-gray-700">Nombre Completo</label>
                    <input type="text" id="nombre" required class="mt-1 w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-semibold text-gray-700">Profesión</label>
                    <input type="text" id="profesion" required class="mt-1 w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-semibold text-gray-700">Estudios Complementarios</label>
                    <input type="text" id="estudios" placeholder="Ej: Maestría en IA, Certificación Scrum" class="mt-1 w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-semibold text-gray-700">Año de Graduación</label>
                        <input type="number" id="anioGraduacion" min="1950" max="2030" required class="mt-1 w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-sm font-semibold text-gray-700">¿Labora actualmente?</label>
                        <select id="labora" onchange="toggleEmpresa()" class="mt-1 w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                            <option value="no">No</option>
                            <option value="si">Sí</option>
                        </select>
                    </div>
                </div>
                <div id="wrapperEmpresa" class="hidden">
                    <label class="block text-sm font-semibold text-gray-700">¿Dónde labora?</label>
                    <input type="text" id="empresa" class="mt-1 w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                </div>
                <div>
                    <label class="block text-sm font-semibold text-gray-700">Experiencia Laboral (Resumen)</label>
                    <textarea id="experiencia" rows="3" required placeholder="Ej: 3 años como Devops en TechCorp..." class="mt-1 w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"></textarea>
                </div>
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg transition duration-200">
                    Agregar a la Bolsa
                </button>
            </form>
        </section>

        <section class="lg:col-span-2">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-2xl font-bold text-gray-900">Profesionales Registrados</h2>
                <span id="counter" class="bg-indigo-100 text-indigo-800 text-xs font-semibold px-2.5 py-1 rounded-full">0 Candidatos</span>
            </div>
            <div id="directory" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
        </section>
    </main>

    <script>
        const API_URL = "http://127.0.0.1:8000/api/profesionales";

        function toggleEmpresa() {
            const labora = document.getElementById('labora').value;
            const wrapper = document.getElementById('wrapperEmpresa');
            if (labora === 'si') {
                wrapper.classList.remove('hidden');
            } else {
                wrapper.classList.add('hidden');
                document.getElementById('empresa').value = '';
            }
        }

        async function renderDirectory() {
            const directory = document.getElementById('directory');
            const counter = document.getElementById('counter');
            directory.innerHTML = '';

            try {
                const response = await fetch(API_URL);
                const profesionales = await response.json();

                counter.textContent = `${profesionales.length} Candidato(s)`;

                if (profesionales.length === 0) {
                    directory.innerHTML = `
                        <div class="col-span-2 text-center py-12 text-gray-500">
                            No hay profesionales registrados actualmente.
                        </div>`;
                    return;
                }

                profesionales.forEach(prof => {
                    const statusBadge = prof.labora 
                        ? `<span class="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded-full">Laborando en: \${prof.empresa}</span>`
                        : `<span class="bg-amber-100 text-amber-800 text-xs font-medium px-2.5 py-0.5 rounded-full">Disponible para contratar</span>`;

                    const card = `
                        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-between hover:shadow-md transition duration-200">
                            <div>
                                <div class="flex justify-between items-start mb-2">
                                    <h3 class="text-lg font-bold text-gray-900">\${prof.nombre}</h3>
                                    <span class="bg-indigo-50 text-indigo-700 text-xs font-bold px-2 py-1 rounded">Grad. \${prof.graduacion}</span>
                                </div>
                                <p class="text-sm font-semibold text-indigo-600 mb-3">\${prof.profesion}</p>
                                <div class="mb-4">\${statusBadge}</div>
                                <div class="space-y-2 text-sm text-gray-600">
                                    <p><strong>Estudios:</strong> \${prof.estudios || 'Ninguno'}</p>
                                    <p class="text-gray-500 italic">"\${prof.experiencia}"</p>
                                </div>
                            </div>
                        </div>
                    `;
                    directory.innerHTML += card;
                });
            } catch (error) {
                console.error("Error al conectar con la API:", error);
                directory.innerHTML = `
                    <div class="col-span-2 text-center py-12 text-red-500">
                        Error al conectar con el servidor. Asegúrate de que FastAPI esté corriendo en http://127.0.0.1:8000.
                    </div>`;
            }
        }

        document.getElementById('professionalForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const nuevoProf = {
                nombre: document.getElementById('nombre').value,
                profesion: document.getElementById('profesion').value,
                estudios: document.getElementById('estudios').value,
                graduacion: parseInt(document.getElementById('anioGraduacion').value),
                labora: document.getElementById('labora').value === 'si',
                empresa: document.getElementById('empresa').value,
                experiencia: document.getElementById('experiencia').value
            };

            try {
                const response = await fetch(API_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(nuevoProf)
                });

                if (response.ok) {
                    renderDirectory();
                    this.reset();
                    document.getElementById('wrapperEmpresa').classList.add('hidden');
                } else {
                    alert("Error al guardar el profesional.");
                }
            } catch (error) {
                console.error("Error en la petición:", error);
            }
        });

        renderDirectory();
    </script>
</body>
</html>
"""
    with open(os.path.join(PROJECT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
    print(" [+] Archivo generado exitosamente: index.html")

    # 5. Generar archivo ZIP de respaldo para ti
    zip_filename = "proyecto_bolsa.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(os.path.join(PROJECT_DIR, "index.html"), arcname="index.html")
        zipf.write(os.path.join(PROJECT_DIR, "main.py"), arcname="main.py")
        zipf.write(os.path.join(PROJECT_DIR, "requirements.txt"), arcname="requirements.txt")
    print(f" [+] ¡Archivo ZIP generado con éxito!: '{zip_filename}'")

    print("\n" + "=" * 60)
    print(" 🎉 PROYECTO LISTO PARA INSTALARSE")
    print("=" * 60)
    print("Sigue estos tres simples pasos para levantar tu plataforma:\n")
    print(f" 1. Entra a la carpeta del proyecto en tu terminal:")
    print(f"    cd {PROJECT_DIR}")
    print("\n 2. Instala las dependencias necesarias de Python:")
    print("    pip install -r requirements.txt")
    print("\n 3. Corre el servidor de desarrollo FastAPI:")
    print("    uvicorn main:app --reload")
    print("\n 4. Abre tu navegador y simplemente haz doble-clic")
    print(f"    en el archivo 'index.html' dentro de la carpeta '{PROJECT_DIR}'")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()