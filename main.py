import numpy as np
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from httpx._types import RequestData
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from starlette.responses import JSONResponse
from idealista_hook import IdealistaHook
from ai_parse import get_llm_result, validate_and_correct_location
from utils import get_area_by_giving_location, to_idealista_multipolygon, create_meter_radius_circle, LocationType
import logging


class PropertyRequest(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_size: Optional[float] = None
    max_size: Optional[float] = None
    neighborhood: Optional[str] = None
    rooms: Optional[int] = None
    bathrooms: Optional[int] = None


app = FastAPI(title="Aura Backend",
              description="Backend que devuelve diferentes propiedades para el frontend de Aura",
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


def get_idealista_properties(prompt_result: dict) -> pd.DataFrame:
    sort_parse = {
        # Defecto es 0
        # Otros estados = 1
        "Alquilada": 2,
        "Nuda propiedad": 3,
        "Ocupada ilegalmente": 4,
    }
    property = IdealistaHook()
    property.update_token()
    status, dict = property.search_properties_by_coordinates(**prompt_result)
    if status is False:
        raise ValueError(dict)
    df = pd.json_normalize(dict['elementList'])
    df[['additional_info_tag', 'additional_info_name']] = df['labels'].apply(
        lambda x: pd.Series([x[0]['name'], x[0]['text']]) if pd.notna(x) and x else pd.Series([None, None]))
    df['status_sort'] = np.where(df['additional_info_name'].isna(), 0,
                                 df['additional_info_name'].map(sort_parse).fillna(1)).astype(int)
    df = df.sort_values(by=['status_sort', 'priceByArea'], ascending=True)
    logging.info(f"Se han encontrado un total de {len(df)} propiedades")
    df = df.replace({np.nan: None})
    return df


DEFAULT_CITY = 'Madrid, España'


@app.post("/new_prompt")
async def new_prompt(request: dict):
    logging.info(request)
    limit = request.get("limit", "200")
    limit = pd.to_numeric(limit)
    try:
        # Step 1: Get initial LLM result
        logging.info(f"Get initial LLM result")
        prompt_result = get_llm_result(request["prompt"])

        # Step 2: Validate and correct location using LLM
        location_validation = {}
        if "locationName" in prompt_result:
            logging.info(f"Validate and correct location using LLM")
            location_validation = validate_and_correct_location(prompt_result["locationName"], DEFAULT_CITY)

            # Use corrected location if confidence is high enough
            if location_validation["confidence"] > 0.7:
                logging.info(f"Using corrected location: {location_validation['corrected_location']}")
            else:
                logging.warning(f"Low confidence location correction: {location_validation['reason']}")
        # Step 4: Enhanced geocoding with multiple fallbacks
        else:
            logging.warning("No locationName found in LLM result; skipping location validation.")
            raise ValueError("No locationName found in LLM result")
        if location_validation == {}:
            location_validation = {
                "corrected_location": DEFAULT_CITY,
                "confidence": 0.0,
                "reason": "No se proporcionó ninguna ubicación para validar",
                "location_type": LocationType.CITY.value
            }

        coordinates = get_area_by_giving_location(location_validation["corrected_location"])
        geojson_str = to_idealista_multipolygon(coordinates)
        prompt_result['shape'] = geojson_str
        # Step 5: Get properties
        df = get_idealista_properties(prompt_result)
        records = df.head(limit).to_dict(orient='records')
        logging.info(f"Propiedades a devolver: {len(records)}")

        return JSONResponse(content=jsonable_encoder(records))
    except Exception as e:
        logging.error(f"Error creating multipolygon: {str(e)}")
        return {
            "success": False,
            "error": str(e),
        }


@app.post("/new_maps")
async def new_maps(request: dict):
    lng = request.get("lng")
    lng = pd.to_numeric(lng)
    lat = request.get("lat")
    lat = pd.to_numeric(lat)
    limit = request.get("limit", "200")
    limit = pd.to_numeric(limit)
    metro = request.get("metro", "1000")
    metro = pd.to_numeric(metro)
    logging.info(f"Creating radius circle around coordinates: lng={lng}, lat={lat}")
    prompt_result_final = {}
    try:
        circle = create_meter_radius_circle(lat, lng, metro)
        multipolygon_str = to_idealista_multipolygon(circle)
        prompt_result_final['shape'] = multipolygon_str
        df = get_idealista_properties(prompt_result_final)
        logging.info("Successfully created multipolygon for 1km radius")
        records = df.head(limit).to_dict(orient='records')
        logging.info(f"Propiedades encontradas: {len(records)}")
        return JSONResponse(content=jsonable_encoder(records))

    except Exception as e:
        logging.error(f"Error creating multipolygon: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "coordinates": {"lng": lng, "lat": lat}
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
curl -X POST "http://localhost:8000/new_maps" -H "Content-Type: application/json" -d "{\"lng\":\"-3.716641\",\"lat\":\"40.427048\"}"
"""
"""
curl -X POST "http://localhost:8000/new_prompt" -H "Content-Type: application/json" -d "{\"prompt\":\"Quiero un piso en norte de madrid\"}"
"""
