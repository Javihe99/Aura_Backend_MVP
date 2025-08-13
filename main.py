from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Aura Backend MVP",
              description="Un backend simple que devuelve una lista de diccionarios",
              version="0.1.0")

# Configurar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringe esto a dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datos de ejemplo (en un proyecto real, esto podría venir de una base de datos)
items = [
    {"id": 1, "name": "Item 1", "description": "Descripción del item 1"},
    {"id": 2, "name": "Item 2", "description": "Descripción del item 2"},
    {"id": 3, "name": "Item 3", "description": "Descripción del item 3"},
    {"id": 4, "name": "Item 4", "description": "Descripción del item 4"},
    {"id": 5, "name": "Item 5", "description": "Descripción del item 5"},
]

@app.get("/")
async def root():
    return {"message": "Bienvenido al Backend MVP de Aura"}

@app.get("/items")
async def get_items():
    """
    Endpoint que devuelve una lista de diccionarios.
    """
    return items

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    """
    Endpoint que devuelve un item específico por su ID.
    """
    for item in items:
        if item["id"] == item_id:
            return item
    return {"error": "Item no encontrado"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
