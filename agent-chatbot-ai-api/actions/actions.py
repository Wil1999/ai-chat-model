from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import re
import json
import requests
import geopandas as gpd
from shapely.geometry import shape
import asyncio
import aiohttp
import ast

class ActionGenerarRecomendacionDeepseek(Action):
    def name(self):
        return "action_generar_recomendacion_deepseek"
    
    async def call_service_ai_agent(self,prompt):
        async with aiohttp.ClientSession() as session:
            payload = {
                     "prompt":prompt
                     }
            async with session.post("http://10.10.50.253:5500/generar",json=payload) as resp:
                data = await resp.json()
                return data["respuesta"]
            
    async def call_service_recommender(self,mensaje):
        async with aiohttp.ClientSession() as session:
            payload = {
                        "mensaje":mensaje,
                        "top_k":1
                      }
            async with session.post("http://localhost:5000/recomendar",json=payload) as resp:
                data = await resp.json()
                return data["recomendaciones"]

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        texto = tracker.latest_message.get("text", "")
        resp_recom = None
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                        "mensaje":texto,
                        "top_k":1
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
                        resp_recom = data["recomendaciones"][0]
                    else:
                        return f"Respuesta inesperada del agent search engine: {data}"
                    
                prompt_final = (
                    f"Tu tarea es analizar el siguiente escenario climático y proporcionar recomendaciones claras, prácticas y basadas en evidencia para proteger a la población,\n"
                    f"Que la respuesta sea como máximo 150 palabras con un mensaje claro y profesional y no actues como robot, para generar las recomendaciones considera la siguiente información:\n"
                    f"Frase clave: {resp_recom['mensaje']},\n"
                    f"{resp_recom['prompt']},\n"
                    f"Dentro de la respuesta considera los siguientes enlaces informativos: {resp_recom['enlaces']},\n"
                )
                payload = {
                    "prompt": prompt_final
                    }
                async with session.post("http://10.10.50.253:5500/generar",json=payload) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return f"Error: código de estado {resp.status}. Detalles: {error_text}"
                    data = await resp.json()
                    if  len(data["respuesta"]) > 0:
                        return data
                    else:
                        return f"Respuesta inesperada del modelo IA: {data}"
        except Exception as e:
            return {"error": e}