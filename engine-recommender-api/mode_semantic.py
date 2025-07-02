from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import pandas as pd
import faiss
import numpy as np

app = Flask(__name__)

# 1. Cargar el dataset
try:
    df = pd.read_csv("datos_meteorologicos.csv",encoding='utf-8')  # Asegúrate de tener las columnas requeridas
except FileNotFoundError:
    raise RuntimeError("El archivo 'recomendacion.csv' no se encontró.")

# 2. Generar embeddings del cuerpo del mensaje
model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
df["input_text"] = df["description"].astype(str) + " " + df["regiones_afectadas"].astype(str) + " " + df["levelName"].astype(str)
corpus = df["input_text"].tolist()
corpus_embeddings = model.encode(corpus, convert_to_numpy=True, show_progress_bar=True)

# 3. Indexar con FAISS
embedding_dim = corpus_embeddings[0].shape[0]
index = faiss.IndexFlatL2(embedding_dim)
index.add(np.array(corpus_embeddings))

# 4. Función de recomendación
def recomendar_respuesta(mensaje_usuario, top_k=1):
    embedding_query = model.encode(mensaje_usuario, convert_to_numpy=True)
    scores, indices = index.search(np.array([embedding_query]), top_k)
    resultados = []
    for idx in indices[0]:
        resultado = {
            "enlaces": df.iloc[idx]["enlaces"],
            "frase": df.iloc[idx]["frase"],
            "prompt": df.iloc[idx]["prompt"]
            }
        resultados.append(resultado)
    return resultados


# 5. Endpoint de la API
@app.route("/recomendar", methods=["POST"])
def api_recomendar():
    data = request.get_json()
    mensaje_usuario = data.get("mensaje")
    top_k = int(data.get("top_k", 1))

    if not mensaje_usuario:
        return jsonify({"error": "Se requiere el campo 'mensaje'"}), 400

    recomendaciones = recomendar_respuesta(mensaje_usuario, top_k=top_k)
    return jsonify({"recomendaciones": recomendaciones})

# 6. Ejecutar la app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
