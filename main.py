from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import json
import re
from google import genai
from datetime import datetime

load_dotenv()

app = FastAPI(title="Mi ChatBot API - UCSS")

# Configuración de Gemini
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODELO_GEMINI = "gemini-3.6-flash"

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    mensaje: str

class ChatResponse(BaseModel):
    respuesta: str
    fuente: str
    timestamp: str

# ============================================
# CARGAR INFORMACIÓN DEL SCRAPING
# ============================================
def cargar_info_scraping():
    try:
        with open('scraper/ucss_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"✅ Información cargada: {type(data)}")
            return data
    except FileNotFoundError:
        print("⚠️ No se encontró scraper/ucss_data.json")
        return {}
    except json.JSONDecodeError:
        print("⚠️ Error al leer scraper/ucss_data.json")
        return {}

# Cargar datos del scraping
DATOS_SCRAPING = cargar_info_scraping()

def extraer_info_util(datos):
    """Extrae y organiza la información del scraping"""
    if not datos:
        return "No se pudo cargar la información de la web."
    
    info_organizada = []
    
    # Si es una lista (como tu archivo)
    if isinstance(datos, list):
        print(f"📚 Procesando {len(datos)} páginas...")
        
        # Buscar páginas específicas por URL
        for item in datos:
            if not isinstance(item, dict):
                continue
                
            url = item.get('url', '').lower()
            titulo = item.get('titulo', '')
            contenido = item.get('contenido_texto', '')
            
            if not contenido:
                continue
            
            # Filtrar páginas útiles (evitar intranet, login, etc.)
            if any(palabra in url for palabra in ['intranet', 'login', 'recuperar', 'cgi-sys', 'suspended']):
                continue
            
            # Identificar páginas por tema
            if 'facultad' in url or 'ingenieria' in url or 'pregrado' in url:
                info_organizada.append(f"📌 {titulo}\n{contenido[:1500]}")
            
            elif 'admision' in url:
                info_organizada.append(f"📌 ADMISIÓN\n{contenido[:1500]}")
            
            elif 'carrera' in url:
                info_organizada.append(f"📌 CARRERAS\n{contenido[:1500]}")
            
            elif 'contacto' in url or 'contactenos' in url:
                info_organizada.append(f"📌 CONTACTO\n{contenido[:1500]}")
    
    # Si es un diccionario
    elif isinstance(datos, dict):
        for key, value in datos.items():
            if isinstance(value, str):
                info_organizada.append(f"{key}: {value[:1500]}")
    
    # Si no se encontró nada, usar lo que haya
    if not info_organizada:
        return str(datos)[:5000]
    
    return "\n\n".join(info_organizada)

INFO_WEB = extraer_info_util(DATOS_SCRAPING)

# ============================================
# INFORMACIÓN BASE (para respuestas rápidas)
# ============================================
INFORMACION_BASE = f"""
UNIVERSIDAD CATÓLICA SEDES SAPIENTIAE (UCSS)

INFORMACIÓN EXTRAÍDA DE LA WEB OFICIAL:
{INFO_WEB}

DATOS GENERALES:
- Fundación: 1999
- Campus principal: Carretera Central Km. 23.6, Ñaña, Lima
- Contacto: (01) 477-6900 | informes@ucss.edu.pe
- Sitio web: https://www.ucss.edu.pe
"""

PROMPT_SISTEMA = """
Eres un asistente virtual de la Universidad Católica Sedes Sapientiae (UCSS).

INFORMACIÓN OFICIAL DE LA UCSS:
{info_base}

REGLAS ESTRICTAS DE RESPUESTA:
1. **RESPONDE DIRECTAMENTE** usando la información proporcionada.
2. Escribe texto plano: no uses Markdown ni incluyas asteriscos, almohadillas, guiones decorativos o separadores.
3. Organiza la respuesta en párrafos breves de una a tres oraciones, dejando una línea en blanco entre párrafos.
4. Si necesitas enumerar información, usa frases cortas separadas por saltos de línea, sin símbolos al inicio.
5. **SI TIENES LA INFORMACIÓN**, respóndela de manera completa y concisa.
6. **SI NO TIENES LA INFORMACIÓN**, indícalo claramente y sugiere contactar a la UCSS.

PREGUNTA DEL USUARIO: {{pregunta}}
"""

def limpiar_respuesta(respuesta):
    """Elimina formato Markdown residual y conserva párrafos legibles."""
    respuesta = respuesta.strip()
    respuesta = re.sub(r'\*{1,3}|`{1,3}|#{1,6}', '', respuesta)
    respuesta = re.sub(r'^\s*[-•]\s+', '', respuesta, flags=re.MULTILINE)
    respuesta = re.sub(r'\n{3,}', '\n\n', respuesta)
    return respuesta.strip()

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        mensaje = request.mensaje
        
        prompt_base = PROMPT_SISTEMA.format(info_base=INFORMACION_BASE)
        prompt_completo = prompt_base.format(pregunta=mensaje)
        
        respuesta = genai_client.models.generate_content(
            model=MODELO_GEMINI,
            contents=prompt_completo
        )
        
        return ChatResponse(
            respuesta=limpiar_respuesta(respuesta.text),
            fuente="Scraping web",
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Estado del sistema"""
    return {
        "status": "online",
        "modelo": MODELO_GEMINI,
        "scraping_cargado": bool(DATOS_SCRAPING),
        "tamano_info_web": len(INFO_WEB)
    }