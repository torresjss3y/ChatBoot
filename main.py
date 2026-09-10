import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import google.generativeai as genai
from pydantic import BaseModel
import time

load_dotenv()

app = FastAPI(title="Mi ChatBot API - UCSS")

API_KEY = os.getenv("GEMINI_API_KEY1")
if not API_KEY:
    raise RuntimeError("❌ Falta GEMINI_API_KEY en el entorno (.env)")

genai.configure(api_key=API_KEY)

MODELOS_GEMINI = [
    "models/gemini-3.6-flash",
]

app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    mensaje: str

class ChatResponse(BaseModel):
    respuesta: str
    fuente: str
    timestamp: str

def cargar_info_scraping():
    rutas = ['ucss_completo.json', 'scraper/ucss_completo.json']
    for ruta in rutas:
        if os.path.exists(ruta):
            try:
                with open(ruta, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"✅ Base de datos cargada ({len(data)} páginas) desde: {ruta}")
                    return data
            except Exception as e:
                print(f"⚠️ Error al leer {ruta}: {e}")
    print("⚠️ No se encontró la base de datos de scraping.")
    return []

DATOS_SCRAPING = cargar_info_scraping()

def corregir_tipeo(texto: str) -> str:
    """Corrige errores de tipeo comunes manteniendo la consulta natural."""
    reemplazos = {
        r'\binfenier\w*': 'ingenieria',
        r'\bfacutl\w*': 'facultad',
        r'\bcarrer\w*': 'carrera',
        r'\badmis\w*': 'admision',
        r'\bpensio\w*': 'pension',
        r'\brequisi\w*': 'requisito',
        r'\bmatricu\w*': 'matricula',
        r'\bbibliot\w*': 'biblioteca'
    }
    for patron, reemplazo in reemplazos.items():
        texto = re.sub(patron, reemplazo, texto)
    return texto

def buscar_contexto_local(consulta: str, top_k: int = 12) -> str:
    """
    Buscador de contexto equilibrado y adaptativo para TODAS las consultas de la UCSS.
    """
    if not DATOS_SCRAPING:
        return "No hay información web local disponible."

    # 1. Normalización y corrección ortográfica
    consulta_limpia = corregir_tipeo(consulta.lower())
    
    # Palabras vacías sin valor semántico
    stopwords = {'como', 'para', 'donde', 'que', 'los', 'las', 'del', 'con', 'una', 'uno', 'sobre', 'dame', 'informacion', 'ucss', 'dime', 'cuales', 'son', 'acerca', 'todas', 'todos'}
    palabras_clave = [p for p in consulta_limpia.split() if len(p) > 2 and p not in stopwords]

    if not palabras_clave:
        palabras_clave = [p for p in consulta_limpia.split() if len(p) > 2]

    coincidencias = []
    urls_vistas = set()

    # 2. Detección dinámica de intenciones generales
    intenciones = {
        'carreras': any(k in consulta_limpia for k in ['carrera', 'carreras', 'facultad', 'escuela', 'pregrado', 'posgrado', 'maestria', 'malla', 'estudiar']),
        'admision': any(k in consulta_limpia for k in ['admision', 'ingreso', 'postular', 'requisito', 'modalidad', 'examen', 'cronograma']),
        'costos': any(k in consulta_limpia for k in ['costo', 'pension', 'precio', 'cuota', 'pago', 'descuento', 'beca', 'escalafón', 'categoria']),
        'tramites': any(k in consulta_limpia for k in ['tramite', 'constancia', 'certificado', 'carnet', 'retiro', 'traslado', 'convalidación', 'titulo', 'bachiller']),
        'servicios': any(k in consulta_limpia for k in ['biblioteca', 'bienestar', 'psicologia', 'bolsa', 'empleo', 'internacional', 'deporte', 'salud']),
        'sedes': any(k in consulta_limpia for k in ['sede', 'sedes', 'filial', 'ubicacion', 'direccion', 'telefono', 'contacto', 'olivos', 'tarma', 'chulucanas', 'huacho', 'atalaya', 'nueva cajamarca'])
    }

    for item in DATOS_SCRAPING:
        if not isinstance(item, dict):
            continue
        
        titulo = item.get("titulo", "").lower()
        texto = item.get("contenido_texto", "").lower()
        url = item.get("url", "").lower()

        # Desduplicar páginas por URL base
        url_base = url.split('?')[0].rstrip('/').replace('/index.php', '')
        if url_base in urls_vistas:
            continue

        # Filtrar páginas del sistema no útiles
        if any(p in url for p in ['login', 'recuperar', 'cgi-sys', 'wp-admin', 'cart', 'checkout']):
            continue

        score = 0

        # 3. Puntuación por coincidencia de palabras clave exactas
        for palabra in palabras_clave:
            if palabra in titulo:
                score += 20  # Gran peso si la palabra clave está en el título
            if palabra in url:
                score += 10
            
            conteo = texto.count(palabra)
            if conteo > 0:
                score += min(conteo * 2, 10) # Peso por frecuencia de palabra en el contenido

        # 4. Boost Inteligente según la intención del usuario
        if intenciones['carreras'] and any(k in url or k in titulo for k in ['carrera', 'facultad', 'escuela', 'pregrado', 'posgrado', 'oferta-academica']):
            score += 25

        if intenciones['admision'] and any(k in url or k in titulo for k in ['admision', 'modalidad', 'requisito', 'postula']):
            score += 25

        if intenciones['costos'] and any(k in url or k in titulo for k in ['pension', 'costo', 'beca', 'pago', 'beneficio']):
            score += 25

        if intenciones['tramites'] and any(k in url or k in titulo for k in ['tramite', 'secretaria', 'guia', 'requisito']):
            score += 25

        if intenciones['servicios'] and any(k in url or k in titulo for k in ['biblioteca', 'bienestar', 'empleabilidad', 'servicio']):
            score += 25

        if intenciones['sedes'] and any(k in url or k in titulo for k in ['sede', 'filial', 'contacto', 'nosotros']):
            score += 25

        # 5. Guardar el documento si obtuvo puntuación válida
        if score > 0:
            urls_vistas.add(url_base)
            coincidencias.append((score, item))

    # Ordenar por relevancia descendente y extraer los mejores resultados
    coincidencias.sort(key=lambda x: x[0], reverse=True)
    mejores = coincidencias[:top_k]

    if not mejores:
        return "No se encontraron detalles específicos en la base de datos."

    contexto = []
    for _, doc in mejores:
        contexto.append(f"📌 **PÁGINA: {doc.get('titulo', 'UCSS')}**\nURL: {doc.get('url')}\n{doc.get('contenido_texto', '')[:3000]}")

    return "\n\n".join(contexto)

INFORMACION_BASE = """
UNIVERSIDAD CATÓLICA SEDES SAPIENTIAE (UCSS)
- Fundación: 1999
- Campus principal: Esquina Constelaciones y Sol de Oro s/n, Urb. Sol de Oro, Los Olivos, Lima - Perú
- Central Telefónica: (01) 604-5000 | informes@ucss.edu.pe
- Sitio web: https://www.ucss.edu.pe
"""
PROMPT_SISTEMA = """
Eres el asistente virtual oficial de la Universidad Católica Sedes Sapientiae (UCSS).
Tu objetivo es brindar respuestas claras, completas y de máxima utilidad al usuario sobre carreras, mallas curriculares, graduación, trámites y servicios.

==================================================
CONTEXTO EXTRAÍDO DE LA UCSS
==================================================
{contexto_web}

==================================================
PREGUNTA DEL USUARIO
==================================================
{pregunta}

==================================================
INSTRUCCIONES DE RESPUESTA
==================================================
1. Revisa detenidamente todo el contexto provisto (incluyendo las secciones de respaldo si existen).
2. Si el usuario pregunta por la malla curricular o cursos de una carrera (ej. Ingeniería de Sistemas), detalla la estructura por áreas o ciclos según la información encontrada. EVITA responder que "no figura" si hay información de asignaturas o áreas disponible.
3. Si la pregunta es sobre graduación o titulación, explica los requisitos generales (créditos, tesis, idiomas, prácticas).
4. Presenta la respuesta con un formato limpio, organizado en viñetas y negritas.

RESPONDE AHORA A LA PREGUNTA DEL USUARIO:
"""

def limpiar_respuesta(respuesta):
    respuesta = re.sub(r'\n{3,}', '\n\n', respuesta)
    return respuesta.strip()

def generar_respuesta_con_reintentos(prompt, max_intentos=3, espera_inicial=2):
    ultimo_error = None
    for intento in range(max_intentos):
        for modelo_nombre in MODELOS_GEMINI:
            try:
                print(f"🔄 Consultando modelo: {modelo_nombre} (Intento {intento+1}/{max_intentos})")
                model = genai.GenerativeModel(modelo_nombre)
                respuesta = model.generate_content(prompt)
                print(f"✅ Respuesta generada con éxito por: {modelo_nombre}")
                return respuesta.text
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Error en {modelo_nombre}: {error_msg}")
                ultimo_error = e
                time.sleep(espera_inicial)
                continue
    
    if ultimo_error:
        raise ultimo_error
    else:
        raise Exception("Ocurrió un problema con los modelos de IA.")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        mensaje = request.mensaje
        
        # Búsqueda adaptativa de contexto
        contexto_web = buscar_contexto_local(mensaje, top_k=12)
        
        prompt_completo = PROMPT_SISTEMA.format(
            contexto_web=contexto_web,
            pregunta=mensaje
        )
        
        respuesta_text = generar_respuesta_con_reintentos(
            prompt=prompt_completo,
            max_intentos=3,
            espera_inicial=2
        )
        
        return ChatResponse(
            respuesta=limpiar_respuesta(respuesta_text),
            fuente="Base de Datos UCSS",
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"❌ Error en endpoint /chat: {e}")
        raise HTTPException(
            status_code=503,
            detail="Servicio temporalmente ocupado. Por favor reintenta en unos segundos."
        )

@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "modelos_disponibles": MODELOS_GEMINI,
        "total_paginas_cargadas": len(DATOS_SCRAPING)
    }