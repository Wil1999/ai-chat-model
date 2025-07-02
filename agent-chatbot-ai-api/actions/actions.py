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
            # resp = requests.post("http://localhost:11434/api/generate", json={"model":"deepseek-coder","prompt": prompt,"stream":False})
            # recomendacion = resp.json().get("respuesta", "No se obtuvo respuesta de la IA.")
            payload = {
                     "model":"deepseek/deepseek-chat-v3-0324",
                     "messages":[
                         {
                         "role": "user",
                         "content": prompt
                         }
                         ]
                     }
            header ={
                "Content-Type": "application/json",
                "Authorization": "Bearer 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"
            }
            async with session.post("https://openrouter.ai/api/v1/chat/completions",json=payload,headers=header) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            
    async def call_service_recommender(self,mensaje):
        async with aiohttp.ClientSession() as session:
            payload = {
                        "mensaje":mensaje,
                        "top_k":1
                      }
            header ={
                "Content-Type": "application/json"
            }
            async with session.post("http://engine-recommender-api:5000/recomendar",json=payload,headers=header) as resp:
                data = await resp.json()
                return data["recomendaciones"]

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        texto = tracker.latest_message.get("text", "")

        intensidad = re.search(r"intensidad.*?:\s*(\w+)", texto)
        contexto = re.search(r"contexto.*?:\s*(\w+)", texto)
        fechas = re.search(r"duración.*?: De (\d{2}/\d{2}/\d{4}) hasta (\d{2}/\d{2}/\d{4})", texto)
        geojson_match = re.search(r"región.*?:\s*(\{.*\})", texto, re.DOTALL)

        intensidad_valor = intensidad.group(1) if intensidad else "DESCONOCIDA"
        fecha_desde = fechas.group(1) if fechas else "?"
        fecha_hasta = fechas.group(2) if fechas else "?"

        try:
            zona_geojson = ast.literal_eval(geojson_match.group(1))
            grupo_afectados = self.find_intersection_peru(zona_geojson)
        except json.JSONDecodeError:
            dispatcher.utter_message("GeoJSON no válido.")
            return []

        prompt = (
            f"Recomienda medidas ante un aviso metereológico con intensidad {intensidad_valor}, "
            f"donde se producirá {contexto}, "
            f"vigente del {fecha_desde} al {fecha_hasta}. Regiones afectadas:\n"
            f"{grupo_afectados}"
        )
        try:
            resp_agent, resp_recomm = await asyncio.gather(
                self.call_service_ai_agent(prompt=prompt),
                self.call_service_recommender(mensaje=prompt)
            )
            recomendacion = {
                                "mensaje": resp_agent,
                                "recomendacion": resp_recomm
                            }
            print("LOGS_SERVICES", recomendacion)
            dispatcher.utter_message(custom=recomendacion)
        except Exception as e:
            dispatcher.utter_message(e)
            recomendacion = f"error: Error al comunicarse con el Asistente IA.\n message: {e}"
        return []
    
    def find_intersection_peru(self,geojson):
        poligono  = shape(geojson["features"][0]["geometry"])
        gdf = gpd.read_file("./peru_provincial_simple.geojson")
        intersect = gdf[gdf.geometry.intersects(poligono)]
        return [f"Provincia: {row.NOMBPROV} - Departamento: {row.FIRST_NOMB}" for _,row in intersect.iterrows()]