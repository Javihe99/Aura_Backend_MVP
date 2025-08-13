# Aura Backend MVP

Un backend simple construido con FastAPI que devuelve una lista de diccionarios, empaquetado con Docker.

## Estructura del proyecto

```
Aura_Backend_MVP/
├── main.py                # Aplicación principal de FastAPI
├── requirements.txt       # Dependencias del proyecto
├── Dockerfile             # Configuración para construir la imagen Docker
├── docker-compose.yml     # Configuración para ejecutar el contenedor
└── .dockerignore          # Archivos a ignorar en el contenedor
```

## Endpoints disponibles

- `GET /`: Mensaje de bienvenida
- `GET /items`: Devuelve la lista completa de items
- `GET /items/{item_id}`: Devuelve un item específico por su ID

## Ejecutar localmente (sin Docker)

1. Crear un entorno virtual:
```
python -m venv .venv
.\.venv\Scripts\activate  # En Windows
```

2. Instalar dependencias:
```
pip install -r requirements.txt
```

3. Ejecutar el servidor:
```
uvicorn main:app --reload
```

4. Visitar http://localhost:8080 en el navegador

## Ejecutar con Docker

1. Construir y ejecutar el contenedor:
```
docker-compose up -d
```

2. Visitar http://localhost:8080 en el navegador

3. Para detener el contenedor:
```
docker-compose down
```

## Documentación de la API

Una vez que el servidor esté en funcionamiento, puedes acceder a la documentación interactiva de la API en:

- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc
