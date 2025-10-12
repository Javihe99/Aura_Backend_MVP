import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
import asyncio
from app.services.supabase_helper import get_supabase_client

logger = logging.getLogger(__name__)


class PropertyManager:
    """Gestor de propiedades usando Supabase"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        if not self.supabase:
            raise Exception("Supabase credentials not configured")
        self._session_cache = {}
        self._cache_ttl = timedelta(minutes=5)
    
    def _get_cache_key(self, session_id: str, limit: int) -> str:
        """Genera clave de caché para sesión y límite"""
        return f"{session_id}:{limit}"
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Verifica si una entrada de caché es válida"""
        if not cache_entry:
            return False
        cache_time = cache_entry.get('timestamp')
        if not cache_time:
            return False
        return datetime.now() - cache_time < self._cache_ttl
    
    def _get_from_cache(self, session_id: str, limit: int) -> Optional[List[Dict]]:
        """Obtiene datos del caché si son válidos"""
        cache_key = self._get_cache_key(session_id, limit)
        cache_entry = self._session_cache.get(cache_key)
        
        if self._is_cache_valid(cache_entry):
            logger.info(f"Cache hit for session {session_id} with limit {limit}")
            return cache_entry.get('data')
        
        if cache_key in self._session_cache:
            del self._session_cache[cache_key]
        
        return None
    
    def _set_cache(self, session_id: str, limit: int, data: List[Dict]) -> None:
        """Guarda datos en el caché"""
        cache_key = self._get_cache_key(session_id, limit)
        self._session_cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now()
        }
        logger.info(f"Cached {len(data)} properties for session {session_id}")
    
    def _extract_nested_data(self, prop: Dict, prefix: str) -> Dict:
        """Extrae datos anidados con un prefijo específico"""
        nested_data = {}
        for key, value in prop.items():
            if key.startswith(f"{prefix}."):
                nested_key = key.replace(f"{prefix}.", "")
                nested_data[nested_key] = value
        return nested_data if nested_data else None
    
    def _prepare_properties_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepara el DataFrame de propiedades para inserción en la base de datos"""
        df_processed = df.copy()
        
        current_time = datetime.now().isoformat()
        df_processed['created_at'] = current_time
        df_processed['updated_at'] = current_time
        column_mapping = {
            'propertyCode': 'propertycode',
            'numPhotos': 'numphotos',
            'propertyType': 'propertytype',
            'locationId': 'locationid',
            'showAddress': 'showaddress',
            'hasVideo': 'hasvideo',
            'newDevelopment': 'newdevelopment',
            'newProperty': 'newproperty',
            'hasLift': 'haslift',
            'priceByArea': 'pricebyarea',
            'hasPlan': 'hasplan',
            'has3DTour': 'has3dtour',
            'has360': 'has360',
            'hasStaging': 'hasstaging',
            'topNewDevelopment': 'topnewdevelopment',
            'newDevelopmentHighlight': 'newdevelopmenthighlight',
            'topPlus': 'topplus',
            'preferenceHighlight': 'preferencehighlight',
            'topHighlight': 'tophighlight',
            'urgentVisualHighlight': 'urgentvisualhighlight',
            'visualHighlight': 'visualhighlight',
            'priceDropValue': 'pricedropvalue',
            'dropDate': 'dropdate',
            'priceDropPercentage': 'pricedroppercentage',
            'newDevelopmentFinished': 'newdevelopmentfinished',
            'highlightComment': 'highlightcomment',
            'externalReference': 'externalreference',
            'savedAd': 'savedad',
            'operation': 'operation',
            'size': 'size',
            'exterior': 'exterior',
            'rooms': 'rooms',
            'bathrooms': 'bathrooms',
            'address': 'address',
            'province': 'province',
            'municipality': 'municipality',
            'district': 'district',
            'country': 'country',
            'neighborhood': 'neighborhood',
            'latitude': 'latitude',
            'longitude': 'longitude',
            'url': 'url',
            'distance': 'distance',
            'description': 'description',
            'status': 'status',
            'favourite': 'favourite',
            'labels': 'labels',
            'ribbons': 'ribbons',
            'notes': 'notes',
            'additionalInfoTag': 'additional_info_tag',
            'additionalInfoName': 'additional_info_name',
            'statusSort': 'status_sort',
            'qualityScore': 'quality_score'
        }
        
        df_processed = df_processed.rename(columns=column_mapping)
        df_processed = df_processed.replace({np.nan: None, np.inf: None, -np.inf: None})
        
        date_columns = ['dropdate', 'created_at', 'updated_at']
        for col in date_columns:
            if col in df_processed.columns:
                df_processed[col] = df_processed[col].apply(self._clean_date_value)
        
        # Columnas esperadas en la base de datos
        expected_columns = [
            'propertycode', 'thumbnail', 'externalreference', 'numphotos', 'floor',
            'price', 'propertytype', 'operation', 'size', 'exterior', 'rooms',
            'bathrooms', 'address', 'province', 'municipality', 'district',
            'country', 'neighborhood', 'locationid', 'latitude', 'longitude',
            'showaddress', 'url', 'distance', 'description', 'description_paraphrased',
            'hasvideo', 'status', 'newdevelopment', 'favourite', 'newproperty', 
            'haslift', 'pricebyarea', 'hasplan', 'has3dtour', 'has360', 'hasstaging', 
            'labels', 'ribbons', 'notes', 'preferencehighlight', 'tophighlight', 
            'topnewdevelopment', 'newdevelopmenthighlight', 'topplus', 
            'urgentvisualhighlight', 'visualhighlight', 'pricedropvalue', 'dropdate', 
            'pricedroppercentage', 'newdevelopmentfinished', 'highlightcomment', 
            'additional_info_tag', 'additional_info_name', 'status_sort', 'quality_score',
            
            # Campos JSONB para objetos anidados
            'priceinfo', 'contactinfo', 'features', 'detailedtype', 'suggestedtexts',
            'multimedia', 'highlight', 'parkingspace', 'savedad',
            
            'created_at', 'updated_at'
        ]
        
        for col in expected_columns:
            if col not in df_processed.columns:
                df_processed[col] = None
        
        # Mapear objetos JSON completos a columnas JSONB
        json_object_mapping = {
            'priceInfo': 'priceinfo',
            'contactInfo': 'contactinfo',
            'features': 'features',
            'detailedType': 'detailedtype',
            'suggestedTexts': 'suggestedtexts',
            'multimedia': 'multimedia',
            'highlight': 'highlight',
            'parkingSpace': 'parkingspace',
            'savedAd': 'savedad'
        }
        
        for json_field, db_field in json_object_mapping.items():
            if json_field in df_processed.columns:
                df_processed[db_field] = df_processed[json_field]
        
        df_processed = df_processed[expected_columns]
        
        return df_processed
    
    def _extract_nested_data_from_row(self, row: pd.Series, prefix: str) -> Dict:
        """Extrae datos anidados de una fila del DataFrame"""
        nested_data = {}
        for key, value in row.items():
            if pd.notna(key) and str(key).startswith(f"{prefix}."):
                nested_key = str(key).replace(f"{prefix}.", "")
                nested_data[nested_key] = value
        return nested_data if nested_data else None
    
    def _clean_date_value(self, value):
        """Limpia valores de fecha para que sean compatibles con PostgreSQL"""
        if pd.isna(value) or value is None:
            return None
        
        try:
            if isinstance(value, (int, float)) and value > 1000000000000:
                timestamp = value / 1000
                if 0 <= timestamp <= 4102444800:
                    return datetime.fromtimestamp(timestamp).isoformat()
                else:
                    return None
            
            elif isinstance(value, str) and value:
                return value
            
            return None
        except (ValueError, OverflowError, OSError):
            return None

    async def save_properties(self, properties: List[Dict]) -> bool:
        """Guarda una lista de propiedades en la base de datos usando upsert"""
        logger.info(f"PropertyManager.save_properties called with {len(properties)} properties")
        
        if not properties:
            logger.warning("No properties provided to save")
            return False
            
        try:
            df = pd.DataFrame(properties)
            logger.info(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
            
            if 'propertyCode' not in df.columns:
                logger.warning("No propertyCode column found in properties data")
                logger.info(f"Available columns: {list(df.columns)}")
                return False
            
            df = df.dropna(subset=['propertyCode'])
            if df.empty:
                logger.warning("No valid properties to save (all missing propertyCode)")
                return False
            
            property_codes = df['propertyCode'].unique().tolist()
            logger.info(f"Processing {len(property_codes)} unique property codes: {property_codes}")
            
            logger.info("Preparing properties dataframe for upsert...")
            df_processed = self._prepare_properties_dataframe(df)
            logger.info(f"Processed DataFrame shape: {df_processed.shape}")
            
            properties_data = df_processed.to_dict('records')
            logger.info(f"Converted to {len(properties_data)} records for upsert")
            
            if properties_data:
                logger.info(f"Upserting {len(properties_data)} properties to database...")
                try:
                    upsert_response = self.supabase.table('properties').upsert(
                        properties_data, 
                        on_conflict='propertycode',
                        ignore_duplicates=False
                    ).execute()
                    logger.info(f"Upsert response: {upsert_response}")
                    logger.info(f"Successfully replaced/inserted {len(properties_data)} properties to database")
                except Exception as upsert_error:
                    logger.error(f"Error during upsert operation: {upsert_error}")
                    logger.info("Attempting to replace existing properties and insert new ones...")
                    try:
                        existing_codes = set()
                        for prop in properties_data:
                            code = prop.get('propertycode')
                            if code:
                                existing_response = self.supabase.table('properties')\
                                    .select('propertycode')\
                                    .eq('propertycode', code)\
                                    .execute()
                                if existing_response.data:
                                    existing_codes.add(code)
                        
                        if existing_codes:
                            self.supabase.table('properties')\
                                .delete()\
                                .in_('propertycode', list(existing_codes))\
                                .execute()
                            logger.info(f"Deleted {len(existing_codes)} existing properties")
                        
                        if properties_data:
                            self.supabase.table('properties').insert(properties_data).execute()
                            logger.info(f"Successfully replaced/inserted {len(properties_data)} properties")
                            
                    except Exception as fallback_error:
                        logger.error(f"Fallback replacement also failed: {fallback_error}")
                        raise upsert_error
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving properties: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def get_properties_by_session(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Obtiene propiedades relacionadas con una sesión específica"""
        
        cached_data = self._get_from_cache(session_id, limit)
        if cached_data is not None:
            return cached_data
            
        try:
            response = self.supabase.table('conversations')\
                .select('metadata')\
                .eq('session_id', session_id)\
                .not_.is_('metadata', 'null')\
                .order('created_at', desc=True)\
                .limit(limit * 2)\
                .execute()
            
            if not response.data:
                self._set_cache(session_id, limit, [])
                return []
            
            property_codes = set()
            for conv in response.data:
                metadata = conv.get('metadata', {})
                property_list = metadata.get('property_list', [])
                if isinstance(property_list, list) and property_list:
                    property_codes.update(property_list)
                    if len(property_codes) >= limit:
                        break
            
            if not property_codes:
                self._set_cache(session_id, limit, [])
                return []
            
            property_codes_list = list(property_codes)[:limit]
            
            properties_response = self.supabase.table('properties')\
                .select('*')\
                .in_('propertycode', property_codes_list)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            result = properties_response.data if properties_response.data else []
            self._set_cache(session_id, limit, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting properties by session: {e}")
            return []
    
    
    async def get_property_by_code(self, property_code: str) -> Optional[Dict]:
        """Obtiene una propiedad específica por su código"""
            
        try:
            response = self.supabase.table('properties')\
                .select('*')\
                .eq('propertycode', property_code)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting property by code: {e}")
            return None
    
    async def get_properties_by_codes(self, property_codes: List[str]) -> Dict[str, List[Dict]]:
        """
        Obtiene propiedades por una lista de property codes.
        
        Args:
            property_codes: Lista de códigos de propiedad a buscar
            
        Returns:
            Dict con 'found_properties' (lista de propiedades encontradas) y 
            'not_found_codes' (lista de códigos no encontrados)
        """
        if not self.supabase or not property_codes:
            return {
                'found_properties': [],
                'not_found_codes': property_codes if property_codes else []
            }
            
        try:
            clean_codes = [str(code).strip() for code in property_codes if str(code).strip()]
            
            if not clean_codes:
                return {
                    'found_properties': [],
                    'not_found_codes': property_codes
                }
            
            logger.info(f"Searching for {len(clean_codes)} property codes: {clean_codes[:5]}{'...' if len(clean_codes) > 5 else ''}")
            
            response = self.supabase.table('properties')\
                .select('*')\
                .in_('propertycode', clean_codes)\
                .execute()
            
            found_properties = response.data if response.data else []
            found_codes = {prop['propertycode'] for prop in found_properties}
            not_found_codes = [code for code in clean_codes if code not in found_codes]
            
            logger.info(f"Found {len(found_properties)} properties, {len(not_found_codes)} not found")
            
            return {
                'found_properties': found_properties,
                'not_found_codes': not_found_codes
            }
            
        except Exception as e:
            logger.error(f"Error getting properties by codes: {e}")
            return {
                'found_properties': [],
                'not_found_codes': property_codes
            }