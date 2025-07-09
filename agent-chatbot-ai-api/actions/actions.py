from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests

class ActionGenerarRecomendacionDeepseek(Action):
    def name(self):
        return "action_generar_recomendacion_deepseek"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        texto = tracker.latest_message.get("text", "")
        resp_recom = None

        try:
            # Llamada al servicio de recomendación
            payload_recom = {
                "mensaje": texto,
                "top_k": 1
            }
            headers = {
                "Content-Type": "application/json"
            }
            response = requests.post("http://localhost:5000/recomendar", json=payload_recom, headers=headers)
            if response.status_code != 200:
                return [dispatcher.utter_message(text=f"Error del servicio de recomendación: {response.status_code}\n{response.text}")]

            data = response.json()
            if "recomendaciones" not in data or not data["recomendaciones"]:
                return [dispatcher.utter_message(text=f"Respuesta inesperada del motor de recomendación: {data}")]

            resp_recom = data["recomendaciones"][0]

            # Construcción del prompt para el modelo IA
            prompt_final = (
                f"Analiza el siguiente escenario climático y ofrece recomendaciones claras, prácticas y basadas en evidencia para proteger a la población. "
                f"Limita tu respuesta a 150 palabras como máximo y emplea un tono profesional y cercano, evitando sonar robótico. "
                f"Considera únicamente la información relevante al escenario climático; si la Frase clave o el Contexto no aportan valor, ignóralos. "
                f"Incluye y referencia este enlace en tu respuesta: {resp_recom['enlaces']}\n\n"
                f"Frase clave: {resp_recom['frase']}\n"
                f"Contexto: {resp_recom['prompt']}"
            )


            payload_ia = {"prompt": prompt_final}
            response_ia = requests.post("http://10.10.50.253:5500/generar", json=payload_ia)
            if response_ia.status_code != 200:
                return [dispatcher.utter_message(text=f"Error del modelo IA: {response_ia.status_code}\n{response_ia.text}")]

            data_ia = response_ia.json()
            raw = data_ia.get("respuesta", "")
            if isinstance(raw, list):
                respuesta_texto = " ".join(str(item) for item in raw)
            else:
                respuesta_texto = str(raw)
            respuesta_texto = respuesta_texto.encode("utf-8", "replace").decode("utf-8")
            dispatcher.utter_message(text=respuesta_texto)
            
        except Exception as e:
            dispatcher.utter_message(text=f"Error al conectar con los servicios: {str(e)}")
            return []
