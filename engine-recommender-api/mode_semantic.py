from flask import Flask, request, jsonify, g
import pandas as pd
import os
import logging
import os
from dotenv import load_dotenv
import requests
import sqlite3
import json
import re
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords
import nltk



load_dotenv()

API_KEY_SCE = os.environ["API_KEY_SEARCH_CUSTOM_ENGINE"]
CX_SEARCH_CUSTOM_ENGINE = os.environ["CX_SEARCH_CUSTOM_ENGINE"]
URL_SCE="https://www.googleapis.com/customsearch/v1"

# Descargar stopwords en español
nltk.download('stopwords')
stopwords_es = stopwords.words('spanish')

# Crear modelo KeyBERT usando modelo multilingüe
kw_model = KeyBERT(model='paraphrase-multilingual-MiniLM-L12-v2')
model_sentence = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

conn = None
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

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

os.environ["TOKENIZERS_PARALLELISM"] = "false"


def init_db():
    global conn
    conn = sqlite3.connect("cache_searchs.db")
    c = conn.cursor()
    sentence = str("""
                   CREATE TABLE IF NOT EXISTS cache_searchs(
                       consulta TEXT PRIMARY KEY,
                       resultados TEXT,
                       embedding TEXT,
                       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   )
                   """)
    c.execute(sentence)
    conn.commit()
    return conn

init_db()

def get_conn():
    if 'db' not in g:
        g.db = sqlite3.connect("cache_searchs.db")
    return g.db


import re

# Diccionarios semánticos base (puedes extenderlos)
RIESGOS = ["lluvia", "granizada", "deslizamiento", "aluvión", "helada", "viento", "tormenta", "inundación", "golpe de calor", "niebla"]
ACCIONES = ["mochila", "botiquín", "refugio", "evacuación", "abrigo", "protección", "revisión", "alerta", "información"]
CONDICIONES = ["clima", "temperatura", "pronóstico", "senamhi", "visibilidad", "estado del tiempo", "sensación térmica"]

# Normalizador
def normalizar(frase):
    frase = frase.lower().strip()
    frase = re.sub(r"[^a-záéíóúñü\s]", "", frase)
    return frase

# Clasificación + verbos guía
def clasificar_y_enriquecer_semantico(frases, top_k=5):
    enriquecidas = []
    for frase in frases:
        f = normalizar(frase)
        if any(p in f for p in RIESGOS):
            enriquecidas.append(f"prevenir {f}")
        elif any(p in f for p in ACCIONES):
            enriquecidas.append(f"recomendar {f}")
        elif any(p in f for p in CONDICIONES):
            enriquecidas.append(f"señalar {f}")
        else:
            enriquecidas.append(f"recomendar {f}")  # fallback general
    return enriquecidas[:top_k]


def guardar_cache(conn, consulta, resultado):
    emb = model_sentence.encode(consulta).tolist()
    conn.execute(
        "REPLACE INTO cache_searchs (consulta, resultados, embedding) VALUES (?, ?, ?)",
        (consulta, json.dumps(resultado), json.dumps(emb))
    )
    conn.commit()

def search_engine_similar(conn, consulta_nueva, umbral=0.65):
    try:
        nueva_emb = model_sentence.encode(consulta_nueva).tolist()
        cur = conn.execute("SELECT consulta, resultados, embedding FROM cache_searchs")
        
        mejor_score = -1
        mejor_resultado = None

        for consulta_antigua, resultados_json, emb_json in cur.fetchall():
            try:
                emb = json.loads(emb_json)
                if not emb:
                    continue
                score = cosine_similarity([nueva_emb], [emb])[0][0]
                if score > mejor_score and score >= umbral:
                    mejor_score = score
                    mejor_resultado = json.loads(resultados_json)
            except Exception as e:
                print(f"[WARNING] Error comparando embeddings: {e}")
                continue
        
        return mejor_resultado
    except Exception as e:
        print(f"[ERROR] Error en fallback de similitud: {e}")
        return []

def recomendar_frases_claves(mensaje_usuario,top_k=1):
    # Extraer frases con 2-3 palabras
    keywords = kw_model.extract_keywords(
        mensaje_usuario,
        keyphrase_ngram_range=(2, 3),
        stop_words=stopwords_es,
        use_mmr=True,
        diversity=0.7,
        top_n=top_k * 3  # más para filtrar
    )

    frases_validas = []
    for frase, _ in keywords:
        tokens = frase.strip().split()
        if len(tokens) >= 2 and not all(t in stopwords_es for t in tokens):
            frases_validas.append(frase)

    if not frases_validas:
        return ["No se encontraron frases significativas"]

    return clasificar_y_enriquecer_semantico(frases_validas, top_k)


def limpiar_datos_search(snippet):
    snippet = re.sub(r"\.{3,}'",'',snippet)
    snippet = re.sub(r"\s+",' ',snippet).strip()
    return snippet

def buscar_en_cache(conn,consulta):
    cur = conn.execute("SELECT resultados FROM cache_searchs WHERE consulta LIKE ?", (f"%{consulta}%",))
    row = cur.fetchone()
    return json.loads(row[0]) if row else None
                   
def search_engine(mensaje,frases_claves, top_k):
    conn = get_conn()
    busqueda_cache = buscar_en_cache(conn, mensaje)
    if busqueda_cache is not None:
        return busqueda_cache
    else:
        try:
            domain_permited= " OR ".join(list_white)
            api_key = API_KEY_SCE
            cx = CX_SEARCH_CUSTOM_ENGINE
            url = URL_SCE
            resp = []
            for f in frases_claves:
                str_f = str(f)
                query =  f"{str_f}, {mensaje} {domain_permited}"
                #query =  f"{str_f} {mensaje}"
                params = {
                    "key": api_key,
                    "cx": cx,
                    "q": query,
                    "num": top_k
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
                                        +f"Pregunta: {mensaje}\n"
                                        +f"Información recuperada: \n{limpiar_datos_search(titulo)} \n{limpiar_datos_search(descripcion)}"
                        }
                    ##
                    resp.append(r_format)
                ##
                try:
                    guardar_cache(conn,mensaje,resp)
                    print(f"Insertado: {titulo}")
                except Exception as e:
                    print(f"Error al insertar datos: {e}")
                
            return resp
        except Exception as e:
            print(f"Se encontró un error al momento de usar el CUSTOM SEARCH ENGINE. \nError: ",e)

@app.route("/recomendar", methods=["POST"])
def api_recomendar():
    data = request.get_json()
    mensaje_usuario = data.get("mensaje")
    top_k = int(data.get("top_k"))

    if not mensaje_usuario:
        return jsonify({"error": "Se requiere el campo 'mensaje'"}), 400
    if not top_k:
        return jsonify({"error": "Se requiere el campo 'top_k'"}), 400
    
    keywords = recomendar_frases_claves(mensaje_usuario, top_k)
    print(f"El modelo predice que la intención es: {keywords}")
    recomendaciones = search_engine(mensaje_usuario,tuple(keywords),1)
    
    return jsonify({"recomendaciones": recomendaciones})

@app.teardown_appcontext
def cerrar_db_conexion(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
