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

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    mensaje = body.get("mensaje")
    prompt = body.get("prompt")
    enlaces = body.get("enlaces")
    
    if prompt == "" and enlaces == "":
        return enviar_a_rasa(mensaje)
    
    prompt_final = (
                f"Analiza el siguiente escenario climático y ofrece recomendaciones claras, prácticas y basadas en evidencia para proteger a la población. "
                f"Limita tu respuesta a 150 palabras como máximo y emplea un tono profesional y cercano, evitando sonar robótico. "
                f"Considera únicamente la información relevante al escenario climático; si la Frase clave o el Contexto no aportan valor, ignóralos. "
                f"Incluye y referencia este enlace en tu respuesta: {enlaces}\n\n"
                f"Frase clave: {mensaje}\n"
                f"Contexto: {prompt}"
            )
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
        f"palabra clave: recomiendame medidas o sugerencias ante avisos metereológicos,\n"
        f"contexto: {titulo +' '+ descripcion},\n"
        f"intensidad del aviso metereológico: {levelName},\n"
        f"duración del aviso metereológico: De {fecha_inicio} hasta {fecha_fin}\n"
        f"región de afectación: {regiones_afectadas}"
    )
    response = await enviar_a_modelo_recomendacion(mensaje)
    return response

def enviar_a_rasa(mensaje):
    payload = {"sender": "usuario123", "message": mensaje}
    resp = requests.post(RASA_WEBHOOK, json=payload)
    return resp.json()

async def enviar_a_modelo_recomendacion(mensaje):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                        "mensaje":mensaje,
                        "top_k":5
                    }
            header ={
                "Content-Type": "application/json"
            }
            async with session.post("http://localhost:5000/recomendar",json=payload,headers=header) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return f"Error: código de estado {resp.status}. Detalles: {error_text}"

                data = await resp.json()
                if "recomendaciones" in data:
                    return data["recomendaciones"]
                else:
                    return f"Respuesta inesperada del modelo: {data}"
    except Exception as e:
        return f"Error al comunicarse con el modelo de recomendación. \n ERROR: {e}"
        
async def enviar_a_agente_ia(prompt):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                    "prompt": prompt
                    }
            async with session.post("http://10.10.50.253:5500/generar",json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return f"Error: código de estado {resp.status}. Detalles: {error_text}"

                data = await resp.json()
                if  len(data["respuesta"]) > 0:
                    return data
                else:
                    return f"Respuesta inesperada del modelo: {data}"
    except Exception as e:
        return f"Error al comunicarse con el agente. \n ERROR: {e}"