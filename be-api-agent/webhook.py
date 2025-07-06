from fastapi import FastAPI, Request
import requests
import ast
from datetime import datetime
import aiohttp
import asyncio
import locale

app = FastAPI()
locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
RASA_WEBHOOK = "http://agent-chatbot-ai-api-rasa-1t:5005/webhooks/rest/webhook"
MODEL_SEMANTIC = "http://engine-recommender-api:5000/recomendar"

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    mensaje = body.get("mensaje")
    prompt = body.get("prompt")
    enlaces = body.get("enlaces")
    
    if prompt == "" and enlaces == "":
        return enviar_a_rasa(mensaje)
    
    prompt_final = (
        f"Actúa como un experto en meteorología y gestión del riesgo climático"
        f"Tu tarea es analizar el siguiente escenario climático y proporcionar recomendaciones claras, prácticas y basadas en evidencia para proteger a la población,\n"
        f"Que la respuesta sea como máximo 150 palabras con un mensaje claro y profesional y no actues como robot, para generar las recomendaciones considera la siguiente información:\n"
        f"Frase clave: {mensaje},\n"
        f"Informacion adicional (prompt basico): {prompt},\n"
        f"Dentro de la respuesta considera los siguientes enlaces informativos: {enlaces},\n"
    )
    response = await enviar_a_agente_ia(prompt=prompt_final)
    return response

@app.get("/parametros")
async def parametros(request: Request):
    body = await request.json()
    levelName = body["nivel"]
    titulo = body["titulo"]
    descripcion = body["descripcion"]
    fecha_inicio = body["fecha_inicio"]
    fecha_fin = body["fecha_fin"]
    
    fecha_inicio_obj = datetime.strptime(fecha_inicio,"%A, %d de %B de %Y a las %H:%M horas")
    fecha_fin_obj = datetime.strptime(fecha_fin, "%A, %d de %B de %Y a las %H:%M horas")

    regiones_afectadas = body["regiones_afectadas"]
    
    region_actual = None
    for region in regiones_afectadas:
        region_date = datetime.strptime(region["date"], "%A, %d de %B de %Y")
        if(fecha_inicio_obj <= region_date <= fecha_fin_obj):
            arr_reg = [f"{n['name']}_{n['provinces']['name']}" for n in region["departments"]]
            region_actual = "- ".join(map(str,arr_reg))
    
    region_actual = region_actual if region_actual == None else "Ya culminó la temporada de alerta, pero recomienda en un contexto más general"
    
    mensaje = (
        f"palabra clave: recomiendame medidas o sugerencias ante avisos metereológicos,\n"
        f"contexto: {titulo +' '+ descripcion},\n"
        f"intensidad del aviso metereológico: {levelName},\n"
        f"duración del aviso metereológico: De {fecha_inicio} hasta {fecha_fin}\n"
        f"región de afectación: {region_actual}"
    )
    response = await enviar_a_modelo_recomendacion(mensaje)
    return response

def enviar_a_rasa(mensaje):
    payload = {"sender": "usuario123", "message": mensaje}
    resp = requests.post(RASA_WEBHOOK, json=payload)
    return resp.json()

async def enviar_a_modelo_recomendacion(mensaje):
    async with aiohttp.ClientSession() as session:
        payload = {
                    "mensaje":mensaje,
                    "top_k":10
                  }
        header ={
            "Content-Type": "application/json"
        }
        async with session.post("http://engine-recommender-api:5000/recomendar",json=payload,headers=header) as resp:
            data = await resp.json()
            return data["recomendaciones"]
        
async def enviar_a_agente_ia(prompt):
    async with aiohttp.ClientSession() as session:
        payload = {
                 "model":"deepseek/deepseek-r1-0528-qwen3-8b:free",
                 "messages":[
                     {
                     "role": "user",
                     "content": prompt
                     }]}
        header ={
            "Content-Type": "application/json",
            "Authorization": "Bearer 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"
            }
        async with session.post("https://openrouter.ai/api/v1/chat/completions",json=payload,headers=header) as resp:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]