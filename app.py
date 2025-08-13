from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AURA MVP Backend", version="0.1.0")

# Ajusta con el dominio de tu frontend (en dev y prod)
origins = [
    "http://localhost",
    "http://localhost:3000",   # REACT
    "http://localhost:5173",   # Vite
    "http://localhost:8080",   # Vue u otros
    # "https://tu-frontend.com",  # prod (por ejemplo)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/items")
async def get_items():
    return [
        {"id": 1, "name": "Alpha", "price": 10.99},
        {"id": 2, "name": "Beta", "price": 12.50},
        {"id": 3, "name": "Gamma", "price": 7.25},
    ]

@app.get("/health")
async def health():
    return {"status": "ok"}
