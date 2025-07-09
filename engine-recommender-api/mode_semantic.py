from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import pandas as pd
import numpy as np
import faiss
import os
from sqlalchemy import create_engine,text
import logging
import subprocess
import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy.exc import IntegrityError

load_dotenv()

SCHEMA = os.environ["SCHEMA"]
STRING_CONNECTION = os.environ["URL_CONNECTION"]
API_KEY_SCE = os.environ["API_KEY_SEARCH_CUSTOM_ENGINE"]
CX_SEARCH_CUSTOM_ENGINE = os.environ["CX_SEARCH_CUSTOM_ENGINE"]
URL_SCE="https://www.googleapis.com/customsearch/v1"

count_repeat_train = 0

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
embedding_dim = 384

index_path = "faiss_index.index"
csv_path = "embeddings.csv"
engine = create_engine(STRING_CONNECTION)

def tarea_reentrenamiento():
    try:
        # Inicializar índice FAISS y corpus
        if os.path.isfile(index_path) and os.path.isfile(csv_path):
            try:
                index = faiss.read_index(index_path)
                df_embeddings = pd.read_csv(csv_path)
                print("Índice FAISS y corpus cargados.")
            except Exception as e:
                print(f"Error al cargar archivos existentes: {e}")
                index = faiss.IndexFlatL2(embedding_dim)
                df_embeddings = pd.DataFrame(columns=["id", "input_text"])
        else:
            index = faiss.IndexFlatL2(embedding_dim)
            df_embeddings = pd.DataFrame(columns=["id", "input_text"])
            print("Se creó un nuevo índice FAISS y corpus vacío.")

        # Conectar a Oracle
        engine = create_engine(STRING_CONNECTION)

        # Obtener la última fecha de entrenamiento
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT MAX(fecha) FROM {SCHEMA}.control_articulos WHERE fuente = 'articulos'")
            )
            ultima_fecha = result.scalar() or datetime(2000, 1, 1)

        # Consultar artículos nuevos desde la base de datos
        query = f"""
        SELECT id, descripcion_completa, titulo, fuente
        FROM {SCHEMA}.articulos_scraping
        WHERE fecha_insercion > TO_TIMESTAMP(:ultima_fecha, 'YYYY-MM-DD HH24:MI:SS')
        """
        nuevos = pd.read_sql(query, con=engine, params={"ultima_fecha": ultima_fecha.strftime("%Y-%m-%d %H:%M:%S")})

        # Filtrar artículos ya indexados
        ids_existentes = set(df_embeddings["id"].astype(int).tolist())
        nuevos = nuevos[~nuevos["id"].isin(ids_existentes)]

        if nuevos.empty:
            print("No hay nuevos artículos para indexar.")
        else:
            # Generar embeddings a partir del contenido
            nuevos["input_text"] = (
                nuevos["titulo"].astype(str) + " " +
                nuevos["descripcion_completa"].astype(str) + " " +
                nuevos["fuente"].astype(str)
            )

            nuevos_embeddings = model.encode(nuevos["input_text"].tolist(), convert_to_numpy=True)

            # Agregar al índice FAISS
            index.add(np.array(nuevos_embeddings))
            faiss.write_index(index, index_path)
            print(f"{len(nuevos)} nuevos embeddings añadidos a FAISS.")

            # Actualizar CSV de embeddings
            df_nuevos = nuevos[["id", "input_text"]]
            df_embeddings = pd.concat([df_embeddings, df_nuevos], ignore_index=True)
            df_embeddings.to_csv(csv_path, index=False, encoding="utf-8")

            # Registrar la nueva ejecución en control_articulos
            with engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {SCHEMA}.control_articulos (fecha, fuente)
                    VALUES (CURRENT_TIMESTAMP, 'articulos')
                """))

            print("Reentrenamiento incremental completado.")
    except Exception as e:
        print(f"Error ejecutando reentrenamiento: {e}")


tarea_reentrenamiento()

if not os.path.isfile(index_path) or not os.path.isfile(csv_path):
    index = faiss.IndexFlatL2(embedding_dim)
    df_embeddings = pd.DataFrame(columns=["id", "text", "embedding"])
else:
    index = faiss.read_index(index_path)
    df_embeddings = pd.read_csv(csv_path)

def search_engine(mensaje_usuario, top_k=5):
    global count_repeat_train
    try:
        api_key = API_KEY_SCE
        cx = CX_SEARCH_CUSTOM_ENGINE
        query = mensaje_usuario
        url = URL_SCE
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": top_k
        }

        def extraer_contenido(url):
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers, timeout=5)
                soup = BeautifulSoup(r.text, "html.parser")
                texto = " ".join([p.get_text(strip=True) for p in soup.select("p")])
                return texto[:1000]
            except Exception as e:
                return f"Error al extraer contenido: {e}"

        response = requests.get(url, params=params)
        data = response.json()
        
        resp = []
        count_repeat_train = 0
        # Extraer solo título, enlace y descripción
        with engine.begin() as conn:
            for item in data.get("items", []):
                titulo = item.get("title")
                enlace = item.get("link")
                descripcion = item.get("snippet")
                descripcion_completa = extraer_contenido(enlace)
                
                ##
                resp.append(
                    {
                        "enlaces":enlace,
                        "frase":titulo,
                        "prompt": "Contexto corto: "+descripcion+"\nContexto general: "+descripcion_completa
                    }
                )
                #
                try:
                    conn.execute(text(f"""
                        INSERT INTO {SCHEMA}.articulos_scraping (
                            titulo, enlace, snippet, descripcion_completa, fuente, fecha_insercion
                        ) VALUES (
                            :titulo, :enlace, :snippet, :descripcion_completa, :fuente, :fecha_insercion
                        )
                    """), {
                        "titulo": titulo,
                        "enlace": enlace,
                        "snippet": descripcion,
                        "descripcion_completa": descripcion_completa,
                        "fuente": "Google Search Engine - GCP - SENAMHITO",
                        "fecha_insercion": datetime.now()
                    })
                    print(f"Insertado: {titulo}")
                except IntegrityError:
                    print(f"Ya existe (duplicado): {enlace}")
        return resp
    except Exception as e:
        print(f"Se encontró un error al momento de usar el CUSTOM SEARCH ENGINE. \nError: ",e)
        if count_repeat_train == 0:
            tarea_reentrenamiento()
        count_repeat_train = count_repeat_train + 1
        return []

def recomendar_respuesta(mensaje_usuario, top_k=1):
    
    rpta_search_engine = search_engine(mensaje_usuario, top_k)
    if rpta_search_engine == []:
        embedding_query = model.encode(mensaje_usuario, convert_to_numpy=True)
        scores, indices = index.search(np.array([embedding_query]), top_k)

        resultados = []
        ids_encontrados = df_embeddings.iloc[indices[0]]["id"].tolist()

        if ids_encontrados:
            ids_str = ",".join([str(i) for i in ids_encontrados])
            query = f"""
            SELECT id, titulo, enlace, snippet, descripcion_completa, fuente
            FROM {SCHEMA}.articulos_scraping
            WHERE id IN ({ids_str})
            """
            try:
                df_resultados = pd.read_sql(query, con=engine)
                for idx in ids_encontrados:
                    fila = df_resultados[df_resultados["id"] == idx]
                    if not fila.empty:
                        fila = fila.iloc[0]
                        resultados.append({
                            "enlaces": fila["enlace"],
                            "frase": fila["titulo"],
                            "prompt": "Contexto corto: "+fila["snippet"]+"\nContexto general: "+fila["descripcion_completa"]
                        })
            except Exception as e:
                print(f"Error en consulta Oracle: {e}")
                return []
    return rpta_search_engine

@app.route("/recomendar", methods=["POST"])
def api_recomendar():
    data = request.get_json()
    mensaje_usuario = data.get("mensaje")
    top_k = int(data.get("top_k"))

    if not mensaje_usuario:
        return jsonify({"error": "Se requiere el campo 'mensaje'"}), 400
    if not top_k:
        return jsonify({"error": "Se requiere el campo 'top_k'"}), 400

    recomendaciones = recomendar_respuesta(mensaje_usuario, top_k=top_k)
    return jsonify({"recomendaciones": recomendaciones})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
