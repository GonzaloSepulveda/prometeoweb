# db.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Aquí pones tu usuario y contraseña directamente
MONGO_URI = "mongodb+srv://topgonzalosepulveda:password!@backendts.ssdd3.mongodb.net/Prometeo?retryWrites=true&w=majority"

client = MongoClient(MONGO_URI)
db = client.get_database("Prometeo")  # nombre de la DB
users_collection = db["Users"]        # colección Users

try:
    client.admin.command('ping')
    print("✅ Conectado a MongoDB")
except ConnectionFailure:
    print("❌ No se pudo conectar a MongoDB")
