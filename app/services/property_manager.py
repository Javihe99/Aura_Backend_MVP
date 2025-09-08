import logging
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client
import os
import pandas as pd

logger = logging.getLogger(__name__)


class PropertyManager:
    """Gestor de propiedades usando Supabase"""
    
    def __init__(self):
        self.supabase = self._init_supabase()
        
    def _init_supabase(self) -> Optional[Client]:
        """Inicializa la conexión con Supabase"""
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not found. Property storage will be disabled.")
                return None
                
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            logger.error(f"Error initializing Supabase: {e}")
            return None
    
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
        # Crear una copia para no modificar el original
        df_processed = df.copy()
        
        # Agregar timestamps
        current_time = datetime.now().isoformat()
        df_processed['created_at'] = current_time
        df_processed['updated_at'] = current_time
        
        # Definir columnas esperadas en la base de datos (usando lowercase como están en la DB)
        expected_columns = [
            'propertycode', 'thumbnail', 'externalreference', 'numphotos', 'floor',
            'price', 'propertytype', 'operation', 'size', 'exterior', 'rooms',
            'bathrooms', 'address', 'province', 'municipality', 'district',
            'country', 'neighborhood', 'locationid', 'latitude', 'longitude',
            'showaddress', 'url', 'distance', 'description', 'hasvideo', 'status',
            'newdevelopment', 'favourite', 'newproperty', 'haslift', 'pricebyarea',
            'hasplan', 'has3dtour', 'has360', 'hasstaging', 'labels', 'ribbons',
            'notes', 'topnewdevelopment', 'topplus', 'preferencehighlight',
            'tophighlight', 'urgentvisualhighlight', 'visualhighlight',
            'pricedropvalue', 'dropdate', 'pricedroppercentage',
            'newdevelopmentfinished', 'highlightcomment', 'additional_info_tag',
            'additional_info_name', 'status_sort', 'quality_score',
            'created_at', 'updated_at'
        ]
        
        # Agregar columnas faltantes con valores None
        for col in expected_columns:
            if col not in df_processed.columns:
                df_processed[col] = None
        
        # Procesar campos anidados usando operaciones vectorizadas
        nested_fields = ['priceInfo', 'contactInfo', 'features', 'detailedType', 
                        'suggestedTexts', 'multimedia', 'highlight', 'parkingSpace']
        
        for field in nested_fields:
            df_processed[field] = df_processed.apply(
                lambda row: self._extract_nested_data_from_row(row, field), 
                axis=1
            )
        
        # Seleccionar solo las columnas esperadas
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
    
    async def save_properties(self, properties: List[Dict]) -> bool:
        """Guarda una lista de propiedades en la base de datos usando pandas para eficiencia"""
        if not self.supabase or not properties:
            return False
            
        try:
            # Convertir a DataFrame para operaciones vectorizadas
            df = pd.DataFrame(properties)
            
            # Filtrar propiedades sin propertycode
            if 'propertycode' not in df.columns:
                logger.warning("No propertycode column found in properties data")
                return False
            
            # Eliminar filas sin propertycode
            df = df.dropna(subset=['propertycode'])
            if df.empty:
                logger.warning("No valid properties to save (all missing propertycode)")
                return False
            
            # Obtener lista de propertycodes únicos
            property_codes = df['propertycode'].unique().tolist()
            logger.info(f"Processing {len(property_codes)} unique property codes")
            
            # Eliminar propiedades existentes con estos propertycodes (operación vectorizada)
            if property_codes:
                delete_response = self.supabase.table('properties').delete().in_('propertycode', property_codes).execute()
                logger.info(f"Deleted {len(property_codes)} existing properties")
            
            # Preparar datos para inserción usando pandas
            df_processed = self._prepare_properties_dataframe(df)
            
            # Convertir DataFrame a lista de diccionarios para inserción
            properties_data = df_processed.to_dict('records')
            
            # Insertar todas las propiedades de una vez (más eficiente)
            if properties_data:
                insert_response = self.supabase.table('properties').insert(properties_data).execute()
                logger.info(f"Inserted {len(properties_data)} new properties to database")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving properties: {e}")
            return False
    
    async def get_properties_by_session(self, session_id: str) -> List[Dict]:
        """Obtiene propiedades relacionadas con una sesión específica"""
        if not self.supabase:
            return []
            
        try:
            # Buscar conversaciones de la sesión que tengan property_list en metadata
            response = self.supabase.table('conversations')\
                .select('metadata')\
                .eq('session_id', session_id)\
                .not_.is_('metadata->property_list', 'null')\
                .execute()
            
            if not response.data:
                return []
            
            # Extraer todos los propertyCodes de las conversaciones
            property_codes = set()
            for conv in response.data:
                metadata = conv.get('metadata', {})
                property_list = metadata.get('property_list', [])
                if isinstance(property_list, list):
                    property_codes.update(property_list)
            
            if not property_codes:
                return []
            
            # Obtener propiedades por propertycode
            properties_response = self.supabase.table('properties')\
                .select('*')\
                .in_('propertycode', list(property_codes))\
                .execute()
            
            return properties_response.data if properties_response.data else []
            
        except Exception as e:
            logger.error(f"Error getting properties by session: {e}")
            return []
    
    async def get_property_by_code(self, property_code: str) -> Optional[Dict]:
        """Obtiene una propiedad específica por su código"""
        if not self.supabase:
            return None
            
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
