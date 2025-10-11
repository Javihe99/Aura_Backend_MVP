import uuid
from typing import Tuple
from urllib.parse import quote_plus
import asyncio

import numpy as np
import pandas as pd

import requests

from app.config import logger
from utils import find_hmac_sha256

NUM_BEDROOMS = [0, 1, 2, 3, 4, 5]
NUM_BATHROOMS = [1, 2, 3]


async def get_idealista_properties(prompt_result: dict) -> (pd.DataFrame, dict):
    """Obtiene propiedades de Idealista usando los parámetros proporcionados de forma ultra-optimizada"""
    
    # Usar nombre de variable no reservada
    idealista_client = IdealistaHook()
    idealista_client.update_token()
    
    # Ejecutar en thread pool para evitar bloqueo
    def _search_wrapper():
        return idealista_client.search_properties_by_coordinates(**prompt_result)
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _search_wrapper)
    status, records = result
    
    if status is False:
        raise ValueError(records)

    # Verificar si hay propiedades encontradas
    if not records.get('elementList') or len(records['elementList']) == 0:
        logger.warning("No se encontraron propiedades con los parámetros especificados")
        # Crear DataFrame vacío con las columnas esperadas
        empty_df = pd.DataFrame(columns=['propertyCode', 'labels', 'priceByArea'])
        empty_df = empty_df.replace({np.nan: None})
        records_copy = records.copy()
        records_copy.pop('elementList', None)
        return empty_df, records_copy

    # OPTIMIZACIÓN CRÍTICA: Procesamiento ultra-rápido
    df = pd.DataFrame(records['elementList'])
    
    # Mantener todos los campos originales de Idealista

    # Procesamiento completo de labels como originalmente
    if 'labels' in df.columns:
        # Usar operaciones vectorizadas en lugar de apply
        df['additional_info_tag'] = None
        df['additional_info_name'] = None
        
        # Procesar solo filas que tienen labels válidos
        valid_labels_mask = df['labels'].notna() & df['labels'].apply(lambda x: isinstance(x, list) and len(x) > 0)
        if valid_labels_mask.any():
            valid_labels = df.loc[valid_labels_mask, 'labels']
            df.loc[valid_labels_mask, 'additional_info_tag'] = valid_labels.apply(lambda x: x[0].get('name') if x else None)
            df.loc[valid_labels_mask, 'additional_info_name'] = valid_labels.apply(lambda x: x[0].get('text') if x else None)
    else:
        # Si no hay columna labels, crear columnas vacías
        df['additional_info_tag'] = None
        df['additional_info_name'] = None

    # Ordenamiento original con status_sort
    sort_parse = {
        # Defecto es 0
        # Otros estados = 1
        "Alquilada": 2,
        "Nuda propiedad": 3,
        "Ocupada ilegalmente": 4,
    }
    
    df['status_sort'] = np.where(df['additional_info_name'].isna(), 0,
                                 df['additional_info_name'].map(sort_parse).fillna(1)).astype(int)
    df = df.sort_values(by=['status_sort', 'priceByArea'], ascending=True)
    
    logger.info(f"Se han encontrado un total de {len(df)} propiedades")
    df = df.replace({np.nan: None})
    
    # Limpieza segura de memoria
    records_copy = records.copy()
    records_copy.pop('elementList', None)
    return df, records_copy


class IdealistaHook:
    def __init__(self):
        self.key = 'bXBUUW5TODhKdFhENmQyRQ=='
        self.public_key = None
        self.user_agent = "Dalvik/2.1.0 (Linux; U; Android 10; Retroid Pocket Mini Build/QKQ1.211001.001)"
        self.jwt_token = None

    def update_token(self):
        url = "https://app.idealista.com/api/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "scope": "write"
        }
        headers = {
            "authorization": "Basic NWI4NWMwM2MxNmJiYjg1ZDk2ZTIzMmIxMTJlZTg1ZGM6aWRlYSUzQmFuZHIwMWQ=",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        form = '&'.join([f"{k}={payload[k]}" for k in sorted(payload.keys())]).encode('utf-8')
        response = requests.post(url, data=form, headers=headers)
        if response and response.status_code == 200:
            response_json = response.json()
            try:
                # print(response_json)
                self.jwt_token = response_json['access_token']
                return True, {
                    "token": self.jwt_token,
                    "text": response.text,
                }
            except Exception as e:
                print(f"Error updating JWT token: {e}")
                return False, {
                    "error": str(e),
                    "status_code": response.status_code,
                }
        else:
            return False, {
                "error": response.text if response else "No response",
                "status_code": response.status_code if response else 500,
            }

    def _send_post_api_request(self, url: str, payload: dict, querystring: dict):

        seed = uuid.uuid4().hex
        message = seed
        message += 'POST'
        message += '&'.join([f"{k}={querystring[k]}" for k in sorted(querystring.keys())])
        payload_arr = []
        for k in sorted(payload.keys()):
            if isinstance(payload[k], str):
                payload_arr.append(f"{k}={quote_plus(payload[k])}")
            else:
                payload_arr.append(f"{k}={payload[k]}")
        message += '&'.join(payload_arr)
        signature = find_hmac_sha256(message, self.key)
        headers = {
            "app_version": "12.17.2",
            "authorization": f"Bearer {self.jwt_token}",
            "signature": signature,
            "seed": seed,
            "user-agent": self.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        full_url = f"{url}?{'&'.join([f'{k}={querystring[k]}' for k in sorted(querystring.keys())])}"
        form = '&'.join([f"{k}={payload[k]}" for k in sorted(payload.keys())]).encode('utf-8')
        response = requests.post(full_url, headers=headers, data=form)

        return response

    def search_properties_by_coordinates(self, **kwargs) -> Tuple[bool, dict]:
        """
        Busca propiedades usando coordenadas de un polígono personalizado
        """

        base_url = f"https://app.idealista.com/api/3.5/{kwargs.get('country', 'es')}/map/search"
        payload = kwargs

        querystring = {
            "t": "",
            "k": ""
        }
        # propertyType is required, default to 'homes'
        payload['propertyType'] = kwargs.get('propertyType', 'homes')
        payload['operation'] = kwargs.get('operation', 'sale')
        payload['locale'] = kwargs.get('locale', 'es')
        payload['quality'] = kwargs.get('quality', 'high')
        payload['order'] = kwargs.get('order', 'ratioeurm2') #Best price per m2
        payload['gallery'] = True


        # Aplicar lógica de sort automático si es necesario
        if kwargs.get("order") == 'floor_desc':
            actual_order = 'floor'
            payload["order"] = actual_order
            payload["sort"] = 'desc'
        elif kwargs.get("order") == 'floor_asc':
            actual_order = 'floor'
            payload["order"] = actual_order
            payload["sort"] = 'asc'
        else:
            actual_order = kwargs.get("order") or 'weigh'
            payload["order"] = actual_order
            # Auto-sort basado en order
            if actual_order == 'weigh':
                payload["sort"] = 'desc'
            elif actual_order == 'publicationDate':
                payload["sort"] = 'desc'
            elif actual_order == 'price':
                payload["sort"] = 'asc'
            elif actual_order == 'ratioeurm2':
                payload["sort"] = 'asc'
            elif actual_order == 'size':
                payload["sort"] = 'desc'
            else:
                actual_order = 'weigh'
                payload["order"] = actual_order
                payload["sort"] = 'desc'

        # Aplicar filtros agrupados
        for param_name, param_value in [
            ('minPrice', kwargs.get('minPrice')),
            ('maxPrice', kwargs.get('maxPrice')),
            ('minSize', kwargs.get('minSize')),
            ('maxSize', kwargs.get('maxSize'))]:
            if param_value is not None and param_value > 0:
                payload[param_name] = float(param_value)

        # Bedrooms y bathrooms
        if kwargs.get('bedrooms'):
            threshold = kwargs.get('bedrooms')
            payload["bedrooms"] = ','.join([str(n) for n in NUM_BEDROOMS if n >= threshold])
        if kwargs.get('bathrooms'):
            payload["bathrooms"] = ','.join([str(n) for n in NUM_BATHROOMS if n >= threshold])
        # Cuando es piso asignamos todos los demás tipo a False
        if kwargs.get('flat'):
            payload["onlyFlats"] = False
            payload["duplex"] = False
            payload["penthouse"] = False

        subtype_house = ['independentHouse', 'semidetachedHouse', 'terracedHouse', 'loftType', 'casaBajaType',
                         'apartamentoType']
        if kwargs.get('chalet'):
            payload["chalet"] = True
        else:
            all_subtypes = [kwargs.get(subtype) for subtype in subtype_house if kwargs.get(subtype) is not None]
            if all_subtypes:
                payload["subTypology"] = ",".join(all_subtypes)
        for i in subtype_house:
            payload.pop(i, None)

        response = self._send_post_api_request(base_url, payload=payload, querystring=querystring)

        if response.status_code == 200:
            try:
                response_json = response.json()
                # print(f"DEBUG: Response JSON keys: {list(response_json.keys())}")
                if 'elementList' in response_json:
                    print(f"DEBUG: Found {len(response_json['elementList'])} elements")
                    pass
                if 'total' in response_json:
                    print(f"DEBUG: Total available: {response_json['total']}")
                    pass
                return True, response_json
            except Exception as e:
                # print(f"DEBUG: Error parsing JSON response: {e}")
                return False, {
                    "error": f"JSON parse error: {e}",
                    "status_code": response.status_code,
                    "raw_response": response.text[:200]
                }
        else:
            print(f"DEBUG: Request failed with status {response.status_code}")
            print(f"DEBUG: Error response: {response.text}")
            return False, {
                "error": response.text,
                "status_code": response.status_code,
            }
