from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests

class ActionGenerarRecomendacionDeepseek(Action):
    def name(self):
        return "action_generar_recomendacion_deepseek"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict):

        texto = tracker.latest_message.get("text", "")
        try:
            # 1. Llamada al servicio de recomendación
            payload_recom = {"mensaje": texto, "top_k": 1}
            resp = requests.post("http://localhost:5000/recomendar",
                                 json=payload_recom,
                                 headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            resp_recom = data["recomendaciones"][0]

            # 2. Construcción del prompt para IA
            prompt_final = (
                f"Analiza el siguiente escenario climático y ofrece recomendaciones claras, "
                f"prácticas y basadas en evidencia para proteger a la población. "
                f"Limita tu respuesta a 150 palabras como máximo y emplea un tono profesional y cercano. "
                f"Considera solo lo relevante; ignora Frase clave o Contexto no útiles. "
                f"Incluye y referencia este enlace: {resp_recom['enlaces']}\n\n"
                f"Frase clave: {resp_recom['frase']}\n"
                f"Contexto: {resp_recom['prompt']}"
            )

            # 3. Llamada al modelo IA
            response_ia = requests.post("http://10.10.50.253:5500/generar",
                                        json={"prompt": prompt_final})
            response_ia.raise_for_status()
            data_ia = response_ia.json()

            # 4. Unificar en un solo texto
            raw = data_ia.get("respuesta", "")
            if isinstance(raw, list):
                raw = " ".join(str(item) for item in raw)
            texto_final = raw.encode("utf-8", "replace").decode("utf-8")

            # 5. Único dispatcher.utter_message
            dispatcher.utter_message(text=texto_final)

        except Exception as e:
            dispatcher.utter_message(
                text=f"Error al conectar con los servicios: {e}"
            )

        # Rasa espera una lista de eventos aunque sea vacía
        return []
