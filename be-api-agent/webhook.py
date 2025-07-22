import re
from fastapi import FastAPI, Request
import requests
import ast
from datetime import datetime
import aiohttp
import asyncio
import locale

app = FastAPI()
locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
RASA_WEBHOOK = "http://localhost:5005/webhooks/rest/webhook"
MODEL_SEMANTIC = "http://localhost:5000/recomendar"

API_KEY_SCE = "AIzaSyAIEUUHD4lTAYMqhr1MnC9UoEtcZC3Ula4"
CX_SEARCH_CUSTOM_ENGINE = "222cc59320c3a4cde"
URL_SCE="https://www.googleapis.com/customsearch/v1"


list_white= ["site:senamhi.gob.pe",
"site:gob.pe",
"site:web2.senamhi.gob.pe",
"site:imarpe.gob.pe",
"site:indeci.gob.pe",
"site:cenepred.gob.pe",
"site:elnacional.com",
"site:minam.gob.pe",
"site:minsa.gob.pe",
"site:pcm.gob.pe",
"site:cruzroja.org.pe",
"site:care.org.pe",
"site:who.int",
"site:noaa.gov",
"site:elcomercio.pe",
"site:larepublica.pe",
"site:infobae.com",
"site:sinagerd.gob.pe",
"site:coen.minsa.gob.pe",
"site:time.is",
"site:24timezones.com"]


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    mensaje = body.get("frase")
    prompt = body.get("prompt")
    enlaces = body.get("enlaces")

    if prompt == "" and enlaces == "":
        #return enviar_a_rasa(mensaje)
        prompt_final = f"""
        Actúa como un experto en optimización de motores de búsqueda (SEO) y recuperación de información. A partir del siguiente texto, genera 1 frase de búsqueda relevante que se podrían usar en una API de search engine para encontrar más información relacionada.
            Las frases deben:
            – Las frases deben parecer consultas reales escritas por usuarios, con lenguaje natural.
            – Reformula el contenido, no lo copies literalmente.
            - Usa términos compuestos, sinónimos o variantes útiles que mejoren la recuperación
            – Sé específico y relevante, pero evita sonar robótico o puro verbos, relaciona cada palabra adecuadamente.
            – Si el texto menciona ubicaciones, eventos o instituciones, incorpóralos de manera contextual y coherente.
            - Considera posibles intenciones del usuario (preguntar, comparar, confirmar, etc.)
            - Filtra temas explícitos, ambiguos, no relacionados o inapropiados. Si el texto no tiene valor informativo o rompe tu objetividad, genera una consulta genérica neutra o indica que no puede generarse una búsqueda útil.

            Texto de origen: 
            "{mensaje}"

            Devuelve solo las frases de búsqueda como una lista sin explicación.
        """
        response = await enviar_a_agente_ia(prompt=prompt_final)
        res = search_engine(mensaje, response)
        result = res[0]
        print(result)
        prompt_pre = (
        f"Considera únicamente la información relevante al escenario climático; si la Frase clave o el Contexto no aportan valor, ignóralos. "
        f"Frase clave: {result['frase']}\n"
        f"{result['prompt']}"
        f"Incluye y referencia este enlace en tu respuesta: {result['enlaces']}\n\n"
        )
        
    else:        
        prompt_pre = (
            f"Considera únicamente la información relevante al escenario climático; si la Frase clave o el Contexto no aportan valor, ignóralos. "
            f"Frase clave: {mensaje}\n"
            f"{prompt}"
            f"Incluye y referencia este enlace en tu respuesta: {enlaces}\n\n"
        )
    prompt_final = f"""
    Actúa como SENAMHITO, un asistente que conoce información sobre meteorología, enfocado en brindar información precisa, actualizada y objetiva sobre condiciones atmosféricas, pronósticos regionales y fenómenos naturales.

    Tu personalidad:
    – Profesional, claro y accesible.
    – Objetivo y neutral en tus respuestas.
    – Con capacidad para dar recomendaciones prácticas sin alarmismo.

    Tus tareas:
    – Responder preguntas relacionadas con clima, alertas, eventos extremos, impacto ambiental, entre otros.
    – Ofrecer sugerencias relevantes según lo consultado (por ejemplo: vestimenta adecuada, medidas preventivas, rutas alternativas, cuidados en caso de neblina o vientos fuertes).
    – Basar todas tus respuestas en principios científicos y datos meteorológicos confiables.
    – Evitar opiniones personales; mantén siempre el enfoque informativo.

    Tu lenguaje debe ser técnico cuando se requiera, pero comprensible para el usuario general. No utilices dramatismos ni exageraciones. Si el usuario pregunta algo fuera del ámbito meteorológico, responde amablemente que estás especializado únicamente en climatología.

    Cuando recibas una consulta, responde de forma clara y útil. Si el mensaje no incluye información meteorológica, pide una aclaración amablemente.
    
    Usuario: {prompt_pre}
    """
    response = await enviar_a_agente_ia(prompt=prompt_final)
    return response


@app.post("/parametros")
async def parametros(request: Request):
    body = await request.json()
    levelName = body["level"]
    titulo = body["title"]
    descripcion = body["description"]
    fecha_inicio = body["startDate"]
    fecha_fin = body["endDate"]
    regiones_afectadas = body["affectedProvinces"]
    regiones_afectadas = ", ".join(str(n) for n in regiones_afectadas)

    mensaje = (
        f"contexto: {titulo +' '+ descripcion},\n"
        f"intensidad del aviso metereológico: {levelName},\n"
        f"duración del aviso metereológico: De {fecha_inicio} hasta {fecha_fin}\n"
        f"región de afectación: {regiones_afectadas}"
    )

    prompt_final = f"""
    Actúa como un experto en optimización de motores de búsqueda (SEO) y recuperación de información. A partir del siguiente texto, genera 5 frases de búsqueda relevantes que se podrían usar en una API de search engine para encontrar más información relacionada.
        Las frases deben:
        – Las frases deben parecer consultas reales escritas por usuarios, con lenguaje natural.
        – Reformula el contenido, no lo copies literalmente.
        - Usa términos compuestos, sinónimos o variantes útiles que mejoren la recuperación
        – Sé específico y relevante, pero evita sonar robótico o puro verbos, relaciona cada palabra adecuadamente.
        – Si el texto menciona ubicaciones, eventos o instituciones, incorpóralos de manera contextual y coherente.
        - Considera posibles intenciones del usuario (preguntar, comparar, confirmar, etc.)

        Texto de origen: 
        "{mensaje}"

        Devuelve solo las frases de búsqueda como una lista sin explicación.
    """
    response = await enviar_a_agente_ia(prompt=prompt_final)
    
    res = search_engine(mensaje, response)
    
    return res


def enviar_a_rasa(mensaje):
    payload = {"sender": "usuario123", "message": mensaje}
    resp = requests.post(RASA_WEBHOOK, json=payload)
    return resp.json()


# async def enviar_a_modelo_recomendacion(mensaje):
#     try:
#         async with aiohttp.ClientSession() as session:
#             payload = {
#                         "mensaje":mensaje,
#                         "top_k":5
#                     }
#             header ={
#                 "Content-Type": "application/json"
#             }
#             async with session.post("http://localhost:5000/recomendar",json=payload,headers=header) as resp:
#                 if resp.status != 200:
#                     error_text = await resp.text()
#                     return f"Error: código de estado {resp.status}. Detalles: {error_text}"

#                 data = await resp.json()
#                 if "recomendaciones" in data:
#                     return data["recomendaciones"]
#                 else:
#                     return f"Respuesta inesperada del modelo: {data}"
#     except Exception as e:
#         return f"Error al comunicarse con el modelo de recomendación. \n ERROR: {e}"


async def enviar_a_agente_ia(prompt):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            headers = {
                "User-Agent": "SenamhitoBot/1.0",
                "Accept": "application/json",
                "X-goog-api-key": "AIzaSyCmWM0SVioUKGjEku3TXdX8F94rpxmb_cc",
            }
            async with session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return (
                        f"Error: código de estado {resp.status}. Detalles: {error_text}"
                    )

                data = await resp.json()
                if len(data["candidates"]) > 0:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    return f"Respuesta inesperada del modelo: {data}"
    except Exception as e:
        return f"Error al comunicarse con el agente. \n ERROR: {e}"

def search_engine(mensaje, frases_claves):
    list_frases_claves = extraer_frases(frases_claves)
    try:
        domain_permited= " OR ".join(list_white)
        api_key = API_KEY_SCE
        cx = CX_SEARCH_CUSTOM_ENGINE
        url = URL_SCE
        resp = []
        for f in list_frases_claves:
            str_f = str(f)
            query =  f"{str_f}, {mensaje} {domain_permited}"
            params = {
                "key": api_key,
                "cx": cx,
                "q": query,
                "num": 1
            }
            response = requests.get(url, params=params)
            data = response.json()
            for item in data.get("items", []):
                titulo = item.get("title")
                enlace = item.get("link")
                descripcion = item.get("snippet")
                r_format = {
                        "enlaces":enlace,
                        "frase": f,
                        "prompt": f"Complementa tu respuesta con esta información:\n"\
                                    +f"Contexto: {mensaje}\n"
                                    +f"Información recuperada: \n{limpiar_datos_search(titulo)} \n{limpiar_datos_search(descripcion)}"
                    }
                ##
                resp.append(r_format)
            ##
        return resp
    except Exception as e:
        print(f"Se encontró un error al momento de usar el CUSTOM SEARCH ENGINE. \nError: ",e)
        
def extraer_frases(texto):
    # Eliminar saltos de línea y dividir por "*"
    fragmentos = re.split(r'\*\s+', texto.strip())

    # Filtrar y limpiar cada frase
    frases = []
    for item in fragmentos:
        if item:
            # Eliminar comillas dobles y espacios extras
            frase_limpia = item.strip().strip('"')
            frases.append(frase_limpia)

    return frases

def limpiar_datos_search(snippet):
    snippet = re.sub(r"(\.{3,}|…|–|-|—)", " ", snippet)
    snippet = snippet.replace('\t', ' ')
    snippet = re.sub(r"[\"\'“”‘’]", '', snippet)
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet.strip()
