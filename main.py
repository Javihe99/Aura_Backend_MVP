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
from ai_parse import get_llm_result
from utils import get_area_by_giving_district, to_idealista_multipolygon
import logging

logging.basicConfig(level=logging.INFO)


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


{}


@app.post("/new_prompt")
async def new_prompt(request: dict):
    logging.info(request)
    limit = request.get("limit", "200")
    limit = pd.to_numeric(limit)
    logging.info("Prompt del usuario: " + request["prompt"])
    logging.info("El limite será: " + str(limit) + " entradas")
    prompt_result = get_llm_result(request["prompt"])
    prompt_result_final = get_llm_result(prompt_result,
                                         system_instruction='Comprueba si locationName es un barrio reconocible por Nominatim o son coordenadas. Si la respuesta es no, cambia al nombre que más se ajuste, deja el resto igual')
    property = IdealistaHook()
    property.update_token()
    coordinates = get_area_by_giving_district(prompt_result["locationName"])
    geojson_str = to_idealista_multipolygon(coordinates)
    prompt_result_final['shape'] = geojson_str
    status, dict = property.search_properties_by_coordinates(**prompt_result_final)

    df = pd.json_normalize(dict['elementList'])
    df = df.replace({np.nan: None})
    records = df.head(limit).to_dict(orient='records')
    logging.info(f"Propiedades encontradas: {len(records)}")
    return JSONResponse(content=jsonable_encoder(records))


@app.get("/2properties")
async def get_2_properties():
    """
    Endpoint que devuelve 10 propiedades de los items.
    """
    properties = [{'propertyCode': '107232992',
                   'thumbnail': 'https://img4.idealista.com/blur/480_360_mq/0/id.pro.es.image.master/fb/36/10/1306922210.webp',
                   'externalReference': 'alm539VM', 'numPhotos': 18, 'floor': 'bj', 'price': 3800000.0,
                   'propertyType': 'flat', 'operation': 'sale', 'size': 316.0, 'exterior': True, 'rooms': 3,
                   'bathrooms': 4, 'address': 'Barrio Almagro', 'province': 'Madrid', 'municipality': 'Madrid',
                   'district': 'Chamberí', 'country': 'es', 'neighborhood': 'Almagro',
                   'locationId': '0-EU-ES-28-07-001-079-07-004', 'latitude': 40.4255737, 'longitude': -3.693789,
                   'showAddress': False, 'url': 'https://www.idealista.com/inmueble/107232992/', 'distance': '1341',
                   'description': 'Olisson presenta esta espectacular vivienda con jardín y piscina privados en el corazón de Almagro, la zona más atractiva del barrio de Chamberí. Este proyecto, desarrollado por Terralpa, combina el carácter clásico de Chamberí con la innovación y el diseño contemporáneo, ofreciendo una vivienda única en el centro de Madrid. El área se caracteriza por los edificios aristocráticos típicos de Chamberí, elegantes y de fachadas clásicas. Conviven con tiendas de diseñadores y artistas emergentes, galerías de arte contemporáneo y restaurantes de moda que marcan el ritmo de Justicia. De la mano del reconocido arquitecto Rafael Robledo, este edificio de obra nueva conserva su fachada clásica y un interior completamente contemporáneo. Se trata de una rehabilitación integral que respeta su fachada y escalera clásicas, proponiendo un levante con un lenguaje propio en su composición, acabado y material, con un carácter neutro y actual. La vivienda, diseñada por el estudio de interiorismo Vilablanch, cuenta con 316 m² y un patio ajardinado recubierto de mármol de 80 m², que conecta con el salón y ofrece gran luminosidad. Dispone de piscina privada y un espacio exterior amplio para disfrutar con amigos y familia. La zona de noche dispone de dos habitaciones familiares en suite y un dormitorio de servicio junto a la cocina. La cocina es de la marca italiana Binova, con puertas en madera natural de nogal Noce Canaletto y vitrinas con diseño personalizado, con marco de nogal y vidrio acanalado. Electrodomésticos de la marca Gaggenau. Los dormitorios familiares se orientan al patio, proporcionando una zona de descanso de total tranquilidad. El vestidor del dormitorio principal es espacioso y acogedor, con gran capacidad de almacenamiento. El interiorismo, cuidado con materiales nobles como la madera, la piedra y los grandes ventanales, crea un espacio cálido y luminoso. Además, cuenta con una cava de vinos para 500 botellas junto al trastero. Ubicada en el barrio de Chamberí, en la confluencia con el barrio de Justicia, también llamado el Soho de Madrid, vivir en esta vivienda con piscina es un auténtico oasis en pleno centro de la ciudad [IW].',
                   'hasVideo': False, 'status': 'good', 'newDevelopment': False, 'priceDropValue': None,
                   'dropDate': None, 'favourite': False, 'newProperty': False, 'hasLift': True,
                   'priceDropPercentage': None, 'priceByArea': 12025.0, 'hasPlan': True, 'has3DTour': False,
                   'has360': False, 'hasStaging': False, 'ribbons': [], 'notes': [], 'topNewDevelopment': False,
                   'topPlus': False, 'preferenceHighlight': False, 'topHighlight': True, 'urgentVisualHighlight': False,
                   'visualHighlight': False, 'priceInfo.price.amount': 3800000.0, 'priceInfo.price.currencySuffix': '€',
                   'priceInfo.price.priceDropInfo.formerPrice': None,
                   'priceInfo.price.priceDropInfo.priceDropValue': None,
                   'priceInfo.price.priceDropInfo.priceDropPercentage': None, 'multimedia.images': [
            {'url': 'https://img4.idealista.com/blur/480_360_mq/0/id.pro.es.image.master/fb/36/10/1306922210.webp',
             'tag': 'livingRoom'}], 'multimedia.videos': None, 'multimedia.virtual3DTours': None,
                   'multimedia.homestagings': None, 'contactInfo.commercialName': 'Olisson Club',
                   'contactInfo.phone1.phoneNumber': '919383085', 'contactInfo.phone1.formattedPhone': '919 38 30 85',
                   'contactInfo.phone1.prefix': '34', 'contactInfo.phone1.phoneNumberForMobileDialing': '+34919383085',
                   'contactInfo.phone1.nationalNumber': True, 'contactInfo.contactName': 'Olisson Club',
                   'contactInfo.userType': 'professional',
                   'contactInfo.agencyLogo': 'https://st3.idealista.com/c8/22/34/olisson.gif',
                   'contactInfo.contactMethod': 'all', 'contactInfo.micrositeShortName': 'olisson',
                   'contactInfo.totalAds': 0, 'contactInfo.needLoginForContact': False,
                   'features.hasSwimmingPool': True, 'features.hasTerrace': False, 'features.hasAirConditioning': True,
                   'features.hasBoxRoom': True, 'features.hasGarden': True, 'detailedType.typology': 'flat',
                   'detailedType.subTypology': None, 'suggestedTexts.subtitle': 'Almagro, Madrid',
                   'suggestedTexts.title': 'Piso', 'highlight.groupDescription': 'Top',
                   'labels': [{'name': 'luxuryType', 'text': 'Lujo'}], 'parkingSpace.hasParkingSpace': None,
                   'parkingSpace.isParkingSpaceIncludedInPrice': None, 'highlightComment': None,
                   'parkingSpace.parkingSpacePrice': None, 'newDevelopmentFinished': None},
                  {'propertyCode': '107739889',
                   'thumbnail': 'https://img4.idealista.com/blur/480_360_mq/0/id.pro.es.image.master/5e/3a/cf/1321745621.webp',
                   'externalReference': '10008474', 'numPhotos': 44, 'floor': '2', 'price': 699000.0,
                   'propertyType': 'flat', 'operation': 'sale', 'size': 130.0, 'exterior': True, 'rooms': 3,
                   'bathrooms': 2, 'address': 'calle del Pez', 'province': 'Madrid', 'municipality': 'Madrid',
                   'district': 'Centro', 'country': 'es', 'neighborhood': 'Malasaña-Universidad',
                   'locationId': '0-EU-ES-28-07-001-079-01-005', 'latitude': 40.4239715, 'longitude': -3.7022017,
                   'showAddress': False, 'url': 'https://www.idealista.com/inmueble/107739889/', 'distance': '786',
                   'description': 'Vivienda2 vende en exclusiva este interesante inmueble exterior con tres balcones a la calle en un edificio del año1890. Situado en la mejor zona del Centro de la capital, el barrio de Malasaña/Universidad, se trata de un piso exterior que consta actualmente de una zona de salón, tres domitorios, una amplia cocina con zona de comedor, con una despensa trastero con gran capacidad de almacenamiento, un cuarto de baño y un aseo. La vivienda se encuentra para reformar y admite un sinfín de posibilidades de redistribución, de ampliar espacios, cambiar la ubicación de diferentes estancias, etc, según las necesidades o deseos del nuevo propietario. No tiene ascensor pero resulta cómodo de subir y pocos gastos de Comunidad. Tiene techos altos, un piso por planta, gas natural para el servicio de agua caliente y suelos antiguos de diferentes dibujos en varias dependencias. Carpintería exterior doble de madera original y de aluminio, puerta interiores originales con cristales antiguos, que le confieren a la casa todo el encanto de otras épocas. Con respecto a la zona en la que se encuentra, comentar que es uno de los barrios con más vida cultural y gastronómica de Madrid, está muy cerca de la calle San Bernardo, de la Gran Vía y de toda la zona comercial de Callao y Preciados. Está muy bien comunicado tanto por Metro como por muchas líneas de la EMT para desplazarse por la capital muy rápidamente y no depender del coche en absoluto. Tenemos plano a escala para ver dichas posibilidades.  ¡No dudes en contactar con nuestros asesores para visitar esta oportunidad tanto para vivir como para invertir y descubrir todas las posibilidades que te ofrece!',
                   'hasVideo': True, 'status': 'renew', 'newDevelopment': False, 'priceDropValue': None,
                   'dropDate': None, 'favourite': False, 'newProperty': False, 'hasLift': False,
                   'priceDropPercentage': None, 'priceByArea': 5377.0, 'hasPlan': True, 'has3DTour': False,
                   'has360': True, 'hasStaging': False, 'ribbons': [], 'notes': [], 'topNewDevelopment': False,
                   'topPlus': False, 'preferenceHighlight': False, 'topHighlight': True, 'urgentVisualHighlight': False,
                   'visualHighlight': False, 'priceInfo.price.amount': 699000.0, 'priceInfo.price.currencySuffix': '€',
                   'priceInfo.price.priceDropInfo.formerPrice': None,
                   'priceInfo.price.priceDropInfo.priceDropValue': None,
                   'priceInfo.price.priceDropInfo.priceDropPercentage': None, 'multimedia.images': [{
                      'url': 'https://img4.idealista.com/blur/480_360_mq/0/id.pro.es.image.master/5e/3a/cf/1321745621.webp',
                      'tag': 'balcony'}],
                   'multimedia.videos': [{'url': 'https://st3v.idealista.com/cb/bc/ea/1321745849.mp4',
                                          'thumbnail': 'https://st3v.idealista.com/cb/bc/ea/d_0_1321745849.jpg',
                                          'multimediaId': 1321745849, 'hasExternalVideoPlayer': False}],
                   'multimedia.virtual3DTours': [{'url': 'https://floorfy.com/tour/2344969?lang=es',
                                                  'thumbnail': 'https://img4.idealista.com/blur/480_360_mq/0/id.pro.es.image.master/5e/3a/cf/1321745621.webp',
                                                  'category': '360'}], 'multimedia.homestagings': None,
                   'contactInfo.commercialName': 'Vivienda2', 'contactInfo.phone1.phoneNumber': '915357200',
                   'contactInfo.phone1.formattedPhone': '915 35 72 00', 'contactInfo.phone1.prefix': '34',
                   'contactInfo.phone1.phoneNumberForMobileDialing': '+34915357200',
                   'contactInfo.phone1.nationalNumber': True, 'contactInfo.contactName': 'Vivienda2',
                   'contactInfo.userType': 'professional',
                   'contactInfo.agencyLogo': 'https://st3.idealista.com/f0/b2/fd/vivienda2.gif',
                   'contactInfo.contactMethod': 'all', 'contactInfo.micrositeShortName': 'vivienda2',
                   'contactInfo.totalAds': 0, 'contactInfo.needLoginForContact': False,
                   'features.hasSwimmingPool': False, 'features.hasTerrace': False,
                   'features.hasAirConditioning': False, 'features.hasBoxRoom': False, 'features.hasGarden': False,
                   'detailedType.typology': 'flat', 'detailedType.subTypology': None,
                   'suggestedTexts.subtitle': 'Malasaña-Universidad, Madrid',
                   'suggestedTexts.title': 'Piso en calle del Pez', 'highlight.groupDescription': 'Top', 'labels': None,
                   'parkingSpace.hasParkingSpace': None, 'parkingSpace.isParkingSpaceIncludedInPrice': None,
                   'highlightComment': None, 'parkingSpace.parkingSpacePrice': None, 'newDevelopmentFinished': None}]

    return properties


@app.get("/0properties")
async def get_0_properties():
    """
    """

    return []


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

    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
curl -X POST "http://localhost:8000/new_prompt" ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"quiero un piso en arguelles\"}"
"""
