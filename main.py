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

# Configuración del cliente de Gemini - Usando la API correcta
genai.configure(api_key=os.getenv("GEMINI_API_KEY2"))

# Modelos Gemini disponibles actualmente
# Basado en los mensajes de error, gemini-3.6-flash es el recomendado
MODELOS_GEMINI = [
    "gemini-3.6-flash",      # Recomendado por los mensajes de error
    "gemini-2.5-flash",      # Alternativa
    "gemini-2.0-flash",      # Alternativa
    "gemini-1.5-flash",      # Alternativa
]

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    mensaje: str

class ChatResponse(BaseModel):
    respuesta: str
    fuente: str
    timestamp: str

# ============================================
# CARGAR INFORMACIÓN DEL SCRAPING (23,000+ PÁGINAS)
# ============================================
def cargar_info_scraping():
    # Intenta cargar desde la raíz o desde la carpeta scraper
    rutas = ['ucss_data.json', 'scraper/ucss_data.json']
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

def buscar_contexto_local(consulta: str, top_k: int = 6) -> str:
    """Buscador optimizado con filtro de relevancia y penalización de páginas genéricas."""
    if not DATOS_SCRAPING:
        return "No hay información web local disponible."

    # Palabras irrelevantes que ensucian la puntuación
    stopwords = {'como', 'para', 'donde', 'que', 'los', 'las', 'del', 'con', 'una', 'uno', 'sobre', 'dame', 'informacion', 'ucss'}
    palabras_consulta = [p.lower() for p in consulta.split() if len(p) > 2 and p.lower() not in stopwords]

    if not palabras_consulta:
        palabras_consulta = [p.lower() for p in consulta.split() if len(p) > 2]

    # Palabras clave genéricas que suelen devolver respuestas vagas
    urls_genericas_a_penalizar = ['/noticias', '/evento', '/bienvenida', '/contacto', '/nosotros', '/galeria']

    coincidencias = []

    for item in DATOS_SCRAPING:
        if not isinstance(item, dict):
            continue
        
        titulo = item.get("titulo", "").lower()
        texto = item.get("contenido_texto", "").lower()
        url = item.get("url", "").lower()

        # Descartar páginas de sistema/desuso
        if any(p in url for p in ['login', 'recuperar', 'cgi-sys', 'wp-admin', 'cart']):
            continue

        score = 0

        # Evaluar coincidencia de frase exacta
        if consulta.lower() in texto:
            score += 15

        for palabra in palabras_consulta:
            if palabra in titulo:
                score += 8  # Mayor peso al título específico
            if palabra in url:
                score += 4
            # Ocurrencias en el texto
            conteo = texto.count(palabra)
            if conteo > 0:
                score += min(conteo, 5)  # Tope para evitar que páginas largas con relleno ganen siempre

        # Penalizar páginas muy genéricas si no coinciden exactamente
        if any(penal in url for penal in urls_genericas_a_penalizar):
            score -= 5

        if score > 0:
            coincidencias.append((score, item))

    # Ordenar por puntaje
    coincidencias.sort(key=lambda x: x[0], reverse=True)
    mejores = coincidencias[:top_k]

    if not mejores:
        return "No se encontraron detalles específicos en la base de datos."

    contexto = []
    for _, doc in mejores:
        # Aumentamos a 2,500 caracteres para entregar la información completa a Gemini
        contexto.append(f"📌 **PÁGINA: {doc.get('titulo', 'UCSS')}**\nURL: {doc.get('url')}\n{doc.get('contenido_texto', '')[:2500]}")

    return "\n\n".join(contexto)

INFORMACION_BASE = """
UNIVERSIDAD CATÓLICA SEDES SAPIENTIAE (UCSS)
- Fundación: 1999
- Campus principal: Carretera Central Km. 23.6, Ñaña, Lima
- Contacto: (01) 477-6900 | informes@ucss.edu.pe
- Sitio web: https://www.ucss.edu.pe
"""

PROMPT_SISTEMA = """
Eres el asistente virtual oficial de la Universidad Católica Sedes Sapientiae (UCSS).
Tu función principal es BRINDAR RESPUESTAS CONCRETAS, COMPLETAS, CLARAS Y ÚTILES sobre la universidad, utilizando EXCLUSIVAMENTE la información disponible en el contexto extraído de las páginas oficiales de la UCSS.
Tu objetivo NO es decirle al usuario que visite la página web para buscar la respuesta.
Tu objetivo es LEER, ANALIZAR, RELACIONAR Y EXTRAER la información disponible para RESPONDER DIRECTAMENTE la duda del usuario.
==================================================
CONTEXTO OFICIAL EXTRAÍDO DE LA UCSS
==================================================
{contexto_web}
==================================================
PREGUNTA DEL USUARIO
==================================================
{pregunta}
==================================================
REGLAS OBLIGATORIAS DE RESPUESTA
==================================================
1. RESPONDE DIRECTAMENTE LA PREGUNTA
No respondas con frases generales como:
- "Puedes consultar nuestra página web."
- "Para más información visita la página oficial."
- "La universidad ofrece diferentes programas."
- "Te recomendamos comunicarte con la universidad."
- "Puedes revisar los requisitos en la página web."
Si la información necesaria aparece en el contexto, DEBES proporcionar esa información directamente.
El usuario está consultando al chatbot precisamente para resolver su duda, por lo que debes intentar resolverla con la información disponible.
--------------------------------------------------
2. UTILIZA TODA LA INFORMACIÓN RELEVANTE DEL CONTEXTO
Antes de responder, analiza todo el contexto proporcionado y selecciona TODA la información relacionada con la pregunta.
No te limites a utilizar únicamente el primer fragmento encontrado.
Si existen varios fragmentos que complementan la respuesta, intégralos en una sola respuesta coherente.
Por ejemplo, si el usuario pregunta por una carrera, y el contexto contiene:
- Nombre de la carrera
- Modalidad
- Duración
- Sede
- Grado académico
- Perfil profesional
- Plan de estudios
- Requisitos
- Costos
- Turnos
- Contacto
Debes incluir toda la información relevante disponible, no solamente el nombre de la carrera.
--------------------------------------------------
3. RESPUESTAS ESPECÍFICAS, NO GENERALES
Evita respuestas vagas, genéricas o demasiado resumidas.
Si el contexto contiene un dato concreto, debes mencionarlo.
Ejemplo:
INCORRECTO: "La carrera tiene una duración determinada."
CORRECTO: "La carrera tiene una duración de 10 semestres."
INCORRECTO: "La universidad cuenta con varias sedes."
CORRECTO: "La carrera se ofrece en las sedes de Lima y Nueva Cajamarca."
--------------------------------------------------
4. NO OMITAS DATOS IMPORTANTES
Cuando estén disponibles en el contexto, incluye explícitamente:
- Nombre completo del programa o carrera.
- Facultad o área académica.
- Sede.
- Modalidad de estudio.
- Duración.
- Grado académico.
- Título profesional.
- Requisitos de admisión.
- Documentos necesarios.
- Fechas importantes.
- Fechas de inscripción.
- Fechas de admisión.
- Costos.
- Pensiones.
- Matrícula.
- Número de cuotas.
- Becas o beneficios.
- Horarios.
- Turnos.
- Plan de estudios.
- Cursos.
- Perfil del egresado.
- Campo laboral.
- Contactos.
- Correos electrónicos.
- Teléfonos.
- Direcciones.
- Horarios de atención.
- Cualquier otro dato específico que esté relacionado con la consulta.
NO inventes información que no aparezca en el contexto.
--------------------------------------------------
5. SI EL USUARIO HACE UNA PREGUNTA AMPLIA
Si el usuario pregunta, por ejemplo: "Quiero información sobre Ingeniería de Sistemas"
No respondas solamente: "Es una carrera de la UCSS."
Debes presentar toda la información relevante disponible en el contexto sobre Ingeniería de Sistemas, organizada por categorías.
Por ejemplo:
**Ingeniería de Sistemas**
- **Modalidad:** ...
- **Duración:** ...
- **Sede:** ...
- **Grado académico:** ...
- **Título profesional:** ...
- **Perfil:** ...
- **Campo laboral:** ...
- **Plan de estudios:** ...
- **Requisitos:** ...
- **Costos:** ...
- **Contacto:** ...
Incluye únicamente las categorías para las cuales exista información en el contexto.
--------------------------------------------------
6. SI EL USUARIO PIDE COMPARAR INFORMACIÓN
Si pregunta:
- "¿Cuál es la diferencia entre X e Y?"
- "¿Qué carrera me conviene?"
- "¿Cuál dura menos?"
- "¿Cuál tiene menor costo?"
- "¿Qué modalidades existen?"
Utiliza la información disponible en el contexto para hacer la comparación directamente.
No obligues al usuario a consultar otras páginas.
Si algún dato necesario para la comparación no aparece en el contexto, indícalo claramente.
--------------------------------------------------
7. SI EL USUARIO PREGUNTA POR REQUISITOS
Debes enumerar TODOS los requisitos que aparezcan en el contexto.
No respondas simplemente: "Debes cumplir con los requisitos de admisión."
Debes indicar cuáles son.
Ejemplo:
**Requisitos de admisión:**
- Documento de identidad.
- Certificado de estudios.
- Pago por derecho de admisión.
Solo incluye requisitos realmente presentes en el contexto.
--------------------------------------------------
8. SI EL USUARIO PREGUNTA POR COSTOS
Si existen datos sobre costos, muéstralos de manera clara.
Por ejemplo:
**Costos:**
- Matrícula: S/ ...
- Pensión: S/ ...
- Número de cuotas: ...
- Derecho de inscripción: S/ ...
NO ocultes los valores cuando estén disponibles.
--------------------------------------------------
9. SI EL USUARIO PREGUNTA POR FECHAS
Las fechas son información crítica.
Debes mencionar las fechas completas disponibles en el contexto.
Por ejemplo:
**Fechas importantes:**
- Inicio de inscripciones: ...
- Cierre de inscripciones: ...
- Examen de admisión: ...
- Inicio de clases: ...
No reemplaces fechas concretas por expresiones como "próximamente" o "en las fechas establecidas".
--------------------------------------------------
10. SI EL USUARIO PREGUNTA POR UNA PERSONA, OFICINA O CONTACTO
Si el contexto contiene nombres, cargos, correos, teléfonos o responsables, debes mostrarlos directamente.
Ejemplo:
**Contacto:**
- Responsable: ...
- Correo: ...
- Teléfono: ...
- Horario de atención: ...
--------------------------------------------------
11. NO DERIVES AL USUARIO A LA PÁGINA WEB SI YA TIENES LA RESPUESTA
Esta regla es MUY IMPORTANTE.
Si la información solicitada aparece en {contexto_web}, responde con esa información.
NO termines automáticamente con: "Para más información visita la página oficial."
La URL solo debe aparecer cuando:
a) El usuario solicite expresamente el enlace.
b) El contexto contenga un enlace que sea realmente necesario para realizar una acción.
c) La información solicitada NO se encuentre en el contexto.
Incluso en esos casos, primero proporciona toda la información que sí tengas.
--------------------------------------------------
12. CUANDO FALTE INFORMACIÓN
Si el contexto no contiene la respuesta, NO INVENTES.
Indica claramente: "No encuentro ese dato en la información oficial disponible para esta consulta."
Si el contexto contiene un correo, teléfono, oficina o URL relacionada con el tema, puedes proporcionarlo como alternativa.
Pero NO uses esta respuesta si la información sí está disponible en el contexto.
--------------------------------------------------
13. NO INVENTES NI SUPONGAS
Está estrictamente prohibido:
- Inventar precios.
- Inventar fechas.
- Inventar requisitos.
- Inventar carreras.
- Inventar cursos.
- Inventar sedes.
- Inventar teléfonos.
- Inventar correos.
- Inventar responsables.
- Inventar horarios.
- Inventar modalidades.
- Completar información mediante suposiciones.
Si un dato no aparece en el contexto, debes indicarlo.
--------------------------------------------------
14. MANTÉN EL CONTEXTO DE LA CONVERSACIÓN
Si el usuario realiza una pregunta de seguimiento, interpreta la pregunta tomando en cuenta la conversación anterior.
Ejemplo:
Usuario: "¿Cuánto dura Ingeniería de Sistemas?"
Chatbot: "La carrera dura 10 semestres."
Usuario: "¿Y cuánto cuesta?"
Debes interpretar que "cuánto cuesta" se refiere a Ingeniería de Sistemas.
No solicites nuevamente información que ya está clara en la conversación.
--------------------------------------------------
15. FORMATO DE RESPUESTA
Utiliza una estructura clara y fácil de leer.
Usa:
- **Negritas** para títulos y datos importantes.
- Listas con guiones.
- Listas numeradas cuando exista un procedimiento o conjunto de pasos.
- Tablas cuando sea necesario comparar varios datos.
No escribas párrafos excesivamente largos.
--------------------------------------------------
16. ADAPTA LA EXTENSIÓN A LA PREGUNTA
Si la pregunta es específica, responde específicamente.
Ejemplo: "¿Cuánto dura la carrera?" -> "**Duración:** 10 semestres."
No es necesario proporcionar información irrelevante.
Si la pregunta es amplia, proporciona una respuesta amplia y completa utilizando toda la información relevante disponible.
--------------------------------------------------
17. PRIORIZA LA UTILIDAD PARA EL USUARIO
Piensa siempre: "¿Qué información necesita el usuario para quedar con su duda resuelta?"
La respuesta debe intentar resolver la consulta en ESTE MENSAJE.
No conviertas al chatbot en un simple intermediario hacia la página web.
--------------------------------------------------
18. RESPUESTA BASADA EN FUENTES OFICIALES
Toda la información debe proceder del contexto extraído de las páginas oficiales de la UCSS.
Si existen contradicciones entre fragmentos del contexto:
- No elijas arbitrariamente.
- Indica la discrepancia.
- Prioriza la información que tenga mayor contexto, fecha más reciente o procedencia más clara, si dicha información está disponible.
--------------------------------------------------
19. REGLA FINAL DE CALIDAD
ANTES DE RESPONDER, realiza internamente estas comprobaciones:
1. ¿Entendí exactamente qué está preguntando el usuario?
2. ¿Busqué la respuesta en TODO el contexto disponible?
3. ¿Estoy incluyendo todos los datos relevantes encontrados?
4. ¿Estoy respondiendo directamente en lugar de enviar al usuario a la web?
5. ¿Estoy evitando información genérica?
6. ¿Estoy evitando inventar información?
7. ¿Estoy manteniendo el contexto de la conversación?
8. ¿La respuesta realmente resuelve la duda del usuario?
Si la respuesta a las preguntas anteriores es sí, responde.
==================================================
RESPONDE AHORA A LA PREGUNTA DEL USUARIO:
{pregunta}
"""

def limpiar_respuesta(respuesta):
    """Limpia excesos de saltos de línea sin destruir la estructura de listas."""
    respuesta = re.sub(r'\n{3,}', '\n\n', respuesta)
    return respuesta.strip()

def generar_respuesta_con_reintentos(prompt, max_intentos=3, espera_inicial=2):
    """Genera respuesta con reintentos automáticos y backoff exponencial."""
    ultimo_error = None
    
    for intento in range(max_intentos):
        for modelo in MODELOS_GEMINI:
            try:
                print(f"🔄 Intentando con modelo: {modelo} (Intento {intento+1}/{max_intentos})")
                respuesta = genai_client.models.generate_content(
                    model=modelo,
                    contents=prompt
                )
                print(f"✅ Éxito con modelo: {modelo}")
                return respuesta.text
                
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Error con {modelo}: {error_msg}")
                
                # Si es error de disponibilidad (503), esperar y continuar
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    tiempo_espera = espera_inicial * (2 ** intento)
                    print(f"⏳ Modelo no disponible. Esperando {tiempo_espera}s...")
                    time.sleep(tiempo_espera)
                    continue
                # Si es error de modelo no encontrado (404), intentar con otro
                elif "404" in error_msg or "NOT_FOUND" in error_msg:
                    continue
                # Otros errores
                else:
                    ultimo_error = e
                    continue
        
        # Si llegamos aquí, todos los modelos fallaron en este intento
        if intento < max_intentos - 1:
            print(f"⏳ Todos los modelos fallaron. Reintentando en {espera_inicial * (2 ** intento)}s...")
            time.sleep(espera_inicial * (2 ** intento))
    
    # Si todos los intentos fallaron
    if ultimo_error:
        raise ultimo_error
    else:
        raise Exception("Todos los modelos fallaron después de múltiples reintentos")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        mensaje = request.mensaje
        
        # Búsqueda semántica/clave en las 23,000 páginas
        contexto_web = buscar_contexto_local(mensaje)

        prompt_completo = PROMPT_SISTEMA.format(
            info_base=INFORMACION_BASE,
            contexto_web=contexto_web,
            pregunta=mensaje
        )
        
        # Generar respuesta con reintentos automáticos
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
        print(f"❌ Error en /chat: {e}")
        # Devolver un mensaje más amigable al usuario
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA está temporalmente ocupado. Por favor, intenta nuevamente en unos segundos."
        )

@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "modelos_disponibles": MODELOS_GEMINI,
        "total_paginas_cargadas": len(DATOS_SCRAPING)
    }