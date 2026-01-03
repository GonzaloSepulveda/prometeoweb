import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator
import requests
import yfinance as yf
import ollama
from pymongo import MongoClient

# ===============================
# CONFIGURACIÓN
# ===============================
API_KEY_NINJA = "qpKu0/GWHz6p0dGkLuwIsA==TRZtzFY80QGpz6sH"
API_URL_NINJA = "https://api.api-ninjas.com/v1/stockprice"
MODEL_NAME = "prometheus"

# ===============================
# MONGO DB (Atlas)
# ===============================
MONGO_URI = "mongodb+srv://topgonzalosepulveda:password!@backendts.ssdd3.mongodb.net/Prometeo?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client["Prometeo"]
users_collection = db["Users"]

try:
    client.admin.command('ping')
    print("✅ Conectado a MongoDB")
except:
    print("❌ No se pudo conectar a MongoDB")

# ===============================
# FASTAPI APP
# ===============================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# MODELOS
# ===============================
class ChatRequest(BaseModel):
    message: str

class UserAuth(BaseModel):
    email: str
    password: str
    isRegister: bool = False

# ===============================
# FUNCIONES AUXILIARES
# ===============================
def is_stock_symbol(text: str):
    t = text.strip().upper()
    return t.isalpha() and 1 <= len(t) <= 6


def get_stock_ninja(symbol: str):
    """ Normaliza la respuesta de API Ninja y evita errores """
    try:
        r = requests.get(
            API_URL_NINJA,
            headers={"X-Api-Key": API_KEY_NINJA},
            params={"ticker": symbol},
            timeout=5
        )
        r.raise_for_status()
        data = r.json()

        if not data:
            return None

        # API Ninja devuelve LISTA → normalizar
        if isinstance(data, list):
            data = data[0]

        if "price" not in data:
            return None

        return {
            "ticker": data.get("ticker", symbol),
            "price": data["price"],
            "timestamp": "N/A"
        }

    except Exception:
        return None


def get_stock_yahoo(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")

        if hist.empty:
            return None

        return {
            "ticker": symbol,
            "price": round(hist["Close"].iloc[-1], 4),
            "timestamp": hist.index[-1].strftime("%Y-%m-%d %H:%M")
        }

    except Exception:
        return None


async def ask_prometheus_stream(prompt: str) -> AsyncGenerator[str, None]:
    """ Maneja streaming seguro de Ollama """
    try:
        for token in ollama.generate(model=MODEL_NAME, prompt=prompt, stream=True):
            if hasattr(token, "delta") and token.delta:
                yield token.delta
            elif hasattr(token, "response") and token.response:
                yield token.response
    except Exception as e:
        yield f"\n❌ Error al generar respuesta con Prometeo: {e}"


# ===============================
# LOGIN / REGISTRO
# ===============================
@app.post("/")
async def login_or_register(user: UserAuth):
    if user.isRegister:
        # Registro
        if users_collection.find_one({"email": user.email}):
            raise HTTPException(status_code=400, detail="Usuario ya existe")

        users_collection.insert_one({
            "email": user.email,
            "password": user.password
        })

        return {"msg": "Usuario registrado correctamente. Ahora inicia sesión."}

    else:
        # Login
        db_user = users_collection.find_one({"email": user.email})

        if not db_user or db_user["password"] != user.password:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        return {"msg": f"Bienvenido {user.email}", "access_token": "dummy_token"}


# ===============================
# ENDPOINT CHAT (NO STREAM)
# ===============================
@app.post("/chat")
async def chat(request: ChatRequest):
    user_input = request.message.strip()

    if is_stock_symbol(user_input):
        symbol = user_input.upper()
        data = get_stock_ninja(symbol) or get_stock_yahoo(symbol)

        if not data:
            return {"response": f"No se pudieron obtener datos para {symbol}"}

        summary = f"""
Símbolo: {data['ticker']}
Precio actual: {data['price']}
Última actualización: {data['timestamp']}
"""

        prompt = f"""
Eres Prometeo, asistente financiero experto.
Analiza estos datos de {symbol} y responde en español:

{summary}
"""
    else:
        prompt = f"""
Eres Prometeo, asistente financiero experto.
El usuario preguntó: "{user_input}"
Responde en español.
"""

    # Generación completa sin stream
    response = ""
    try:
        for chunk in ollama.generate(model=MODEL_NAME, prompt=prompt, stream=True):
            if hasattr(chunk, "delta") and chunk.delta:
                response += chunk.delta
            elif hasattr(chunk, "response") and chunk.response:
                response += chunk.response
    except:
        response = "❌ Error al generar respuesta con Prometeo"

    return {"response": response}


# ===============================
# ENDPOINT CHAT STREAM
# ===============================
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    user_input = request.message.strip()

    if is_stock_symbol(user_input):
        symbol = user_input.upper()
        data = get_stock_ninja(symbol) or get_stock_yahoo(symbol)

        if not data:
            async def error_gen():
                yield f"No se pudieron obtener datos para {symbol}"
            return StreamingResponse(error_gen(), media_type="text/plain")

        summary = f"""
Símbolo: {data['ticker']}
Precio actual: {data['price']}
Última actualización: {data['timestamp']}
"""

        prompt = f"""
Eres Prometeo, asistente financiero experto.
Analiza estos datos de {symbol} y responde en español:

{summary}
"""
    else:
        prompt = f"""
Eres Prometeo, asistente financiero experto.
El usuario preguntó: "{user_input}"
Responde en español.
"""

    return StreamingResponse(
        ask_prometheus_stream(prompt),
        media_type="text/plain"
    )
