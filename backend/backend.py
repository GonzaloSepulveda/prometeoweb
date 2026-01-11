import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator
import requests
import yfinance as yf
import ollama
from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId

# ===============================
# CONFIGURACIÓN
# ===============================
API_KEY_NINJA = os.environ.get("API_KEY_NINJA", "TU_API_KEY")
API_URL_NINJA = "https://api.api-ninjas.com/v1/stockprice"
MODEL_NAME = "prometheus"
MONGO_URI = "mongodb+srv://topgonzalosepulveda:password!@backendts.ssdd3.mongodb.net/Prometeo?retryWrites=true&w=majority"

# ===============================
# MONGO DB
# ===============================
client = MongoClient(MONGO_URI)
db = client["Prometeo"]
users_collection = db["Users"]
conversations_collection = db["Conversations"]
messages_collection = db["Messages"]

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

class ConversationRequest(BaseModel):
    title: str = None

class MessageRequest(BaseModel):
    conversation_id: str
    message: str

# ===============================
# AUTENTICACIÓN SIMPLE
# ===============================
async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido")
    token = authorization[7:]  # quitamos "Bearer "
    user = users_collection.find_one({"email": token})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    return user

# ===============================
# FUNCIONES AUXILIARES
# ===============================
def is_stock_symbol(text: str):
    t = text.strip().upper()
    return t.isalpha() and 1 <= len(t) <= 6

def get_stock_ninja(symbol: str):
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
        if isinstance(data, list):
            data = data[0]
        if "price" not in data:
            return None
        return {"ticker": data.get("ticker", symbol), "price": data["price"], "timestamp": "N/A"}
    except:
        return None

def get_stock_yahoo(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        return {"ticker": symbol, "price": round(hist["Close"].iloc[-1], 4), "timestamp": hist.index[-1].strftime("%Y-%m-%d %H:%M")}
    except:
        return None

async def ask_prometheus_stream(prompt: str) -> AsyncGenerator[str, None]:
    try:
        for token in ollama.generate(model=MODEL_NAME, prompt=prompt, stream=True):
            if hasattr(token, "delta") and token.delta:
                yield token.delta
            elif hasattr(token, "response") and token.response:
                yield token.response
    except Exception as e:
        yield f"\n❌ Error al generar respuesta con Prometeo: {e}"

async def save_message(user_id: str, conversation_id: str, role: str, content: str):
    messages_collection.insert_one({
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "timestamp": datetime.now()
    })
    update_fields = {"updated_at": datetime.now()}
    if role == "user":
        update_fields["title"] = content[:50]
    conversations_collection.update_one({"_id": ObjectId(conversation_id), "user_id": user_id}, {"$set": update_fields})

# ===============================
# LOGIN / REGISTRO
# ===============================
@app.post("/")
async def login_or_register(user: UserAuth):
    if user.isRegister:
        if users_collection.find_one({"email": user.email}):
            raise HTTPException(status_code=400, detail="Usuario ya existe")
        users_collection.insert_one({"email": user.email, "password": user.password})
        return {"msg": "Usuario registrado correctamente. Ahora inicia sesión."}
    else:
        db_user = users_collection.find_one({"email": user.email})
        if not db_user or db_user["password"] != user.password:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        # token = email
        return {"msg": f"Bienvenido {user.email}", "access_token": user.email}

# ===============================
# CONVERSACIONES
# ===============================
@app.post("/conversations")
async def create_conversation(request: ConversationRequest, current_user=Depends(get_current_user)):
    conv = {
        "title": request.title or "Nueva conversación",
        "user_id": str(current_user["_id"]),
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    result = conversations_collection.insert_one(conv)
    return {"conversation_id": str(result.inserted_id), "title": conv["title"]}

@app.get("/conversations")
async def list_conversations(current_user=Depends(get_current_user)):
    convs = conversations_collection.find({"user_id": str(current_user["_id"])}).sort("updated_at", -1)
    return [{"conversation_id": str(c["_id"]), "title": c.get("title", "Sin título"), "updated_at": c.get("updated_at")} for c in convs]

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, current_user=Depends(get_current_user)):
    messages_collection.delete_many({"conversation_id": conversation_id, "user_id": str(current_user["_id"])})
    result = conversations_collection.delete_one({"_id": ObjectId(conversation_id), "user_id": str(current_user["_id"])})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"msg": "Conversación eliminada correctamente"}

# ===============================
# MENSAJES
# ===============================
@app.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, current_user=Depends(get_current_user)):
    # verificar que la conversación pertenece al usuario
    conv = conversations_collection.find_one({"_id": ObjectId(conversation_id), "user_id": str(current_user["_id"])})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    msgs = messages_collection.find({"conversation_id": conversation_id, "user_id": str(current_user["_id"])}).sort("timestamp", 1)
    return [{"role": m.get("role"), "content": m.get("content"), "timestamp": m.get("timestamp")} for m in msgs]

@app.post("/chat_with_history")
async def chat_with_history(request: MessageRequest, current_user=Depends(get_current_user)):
    user_input = request.message.strip()
    conv_id = request.conversation_id

    await save_message(str(current_user["_id"]), conv_id, "user", user_input)

    if is_stock_symbol(user_input):
        symbol = user_input.upper()
        data = get_stock_ninja(symbol) or get_stock_yahoo(symbol)
        if not data:
            resp_text = f"No se pudieron obtener datos para {symbol}"
            await save_message(str(current_user["_id"]), conv_id, "bot", resp_text)
            return {"response": resp_text}
        summary = f"Símbolo: {data['ticker']}\nPrecio: {data['price']}\nÚltima actualización: {data['timestamp']}"
        prompt = f"Eres Prometeo, asistente financiero experto.\nAnaliza estos datos de {symbol} y responde en español:\n{summary}"
    else:
        prompt = f"Eres Prometeo, asistente financiero experto.\nEl usuario preguntó: '{user_input}'\nResponde en español."

    response = ""
    try:
        for chunk in ollama.generate(model=MODEL_NAME, prompt=prompt, stream=True):
            if hasattr(chunk, "delta") and chunk.delta:
                response += chunk.delta
            elif hasattr(chunk, "response") and chunk.response:
                response += chunk.response
    except:
        response = "❌ Error al generar respuesta con Prometeo"

    await save_message(str(current_user["_id"]), conv_id, "bot", response)
    return {"response": response}

@app.post("/chat_with_history/stream")
async def chat_stream_with_history(request: MessageRequest, current_user=Depends(get_current_user)):
    user_input = request.message.strip()
    conv_id = request.conversation_id
    await save_message(str(current_user["_id"]), conv_id, "user", user_input)

    if is_stock_symbol(user_input):
        symbol = user_input.upper()
        data = get_stock_ninja(symbol) or get_stock_yahoo(symbol)
        if not data:
            async def error_gen():
                yield f"No se pudieron obtener datos para {symbol}"
            return StreamingResponse(error_gen(), media_type="text/plain")
        summary = f"Símbolo: {data['ticker']}\nPrecio: {data['price']}\nÚltima actualización: {data['timestamp']}"
        prompt = f"Eres Prometeo, asistente financiero experto.\nAnaliza estos datos de {symbol} y responde en español:\n{summary}"
    else:
        prompt = f"Eres Prometeo, asistente financiero experto.\nEl usuario preguntó: '{user_input}'\nResponde en español."

    async def generator():
        accumulated_text = ""
        try:
            async for token in ask_prometheus_stream(prompt):
                accumulated_text += token
                yield token
            await save_message(str(current_user["_id"]), conv_id, "bot", accumulated_text)
        except Exception as e:
            error_msg = f"\n❌ Error al generar respuesta con Prometeo: {e}"
            await save_message(str(current_user["_id"]), conv_id, "bot", error_msg)
            yield error_msg

    return StreamingResponse(generator(), media_type="text/plain")
