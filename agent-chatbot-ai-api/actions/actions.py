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
                f"Tu tarea es analizar el siguiente escenario climático y proporcionar recomendaciones claras, prácticas y basadas en evidencia para proteger a la población,\n"
                f"Que la respuesta sea como máximo 150 palabras con un mensaje claro y profesional y no actúes como robot, para generar las recomendaciones considera la siguiente información:\n"
                f"Frase clave: {resp_recom['frase']},\n"
                f"{resp_recom['prompt']},\n"
                f"Dentro de la respuesta considera los siguientes enlaces informativos: {resp_recom['enlaces']},\n"
            )

            payload_ia = {"prompt": prompt_final}
            response_ia = requests.post("http://10.10.50.253:5500/generar", json=payload_ia)
            if response_ia.status_code != 200:
                return [dispatcher.utter_message(text=f"Error del modelo IA: {response_ia.status_code}\n{response_ia.text}")]

            data_ia = response_ia.json()
            respuesta_modelo = data_ia.get("respuesta", [])

           # Si es lista, unir todo en un solo texto
            if isinstance(respuesta_modelo, list):
                texto_unico = "\n\n".join(respuesta_modelo)
                dispatcher.utter_message(text=texto_unico)
            elif isinstance(respuesta_modelo, str):
                dispatcher.utter_message(text=respuesta_modelo)
            else:
                dispatcher.utter_message(text=f"Respuesta inesperada del modelo IA: {data_ia}")

        except Exception as e:
            dispatcher.utter_message(text=f"Error al conectar con los servicios: {str(e)}")
            return []
