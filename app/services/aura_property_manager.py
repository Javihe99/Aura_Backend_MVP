import logging
import random
from typing import List, Dict, Optional
from supabase import create_client, Client
import os

logger = logging.getLogger(__name__)


class AuraPropertyManager:
    """Gestor de propiedades exclusivas de Aura"""
    
    def __init__(self):
        self.supabase = self._init_supabase()
        
    def _init_supabase(self) -> Client:
        """Inicializa la conexión con Supabase"""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not supabase_url or not supabase_key:
            logger.error("Supabase credentials not found in environment variables")
            raise Exception("Supabase credentials not configured")
            
        return create_client(supabase_url, supabase_key)
    
    async def get_exclusive_properties_random(self) -> List[Dict]:
        """
        Obtiene todas las propiedades exclusivas de Aura en orden aleatorio.
        
        Returns:
            List[Dict]: Lista de propiedades en orden aleatorio
        """
        try:
            logger.info("Fetching exclusive Aura properties in random order...")
            
            # Obtener todas las propiedades de la tabla aura_properties
            response = self.supabase.table('aura_properties')\
                .select('*')\
                .execute()
            
            if not response.data:
                logger.warning("No exclusive properties found in aura_properties table")
                return []
            
            # Convertir a lista y mezclar aleatoriamente
            properties = list(response.data)
            random.shuffle(properties)
            
            logger.info(f"Retrieved {len(properties)} exclusive properties in random order")
            return properties
            
        except Exception as e:
            logger.error(f"Error getting exclusive properties: {e}")
            return []
    
    async def get_exclusive_property_by_code(self, property_code: str) -> Optional[Dict]:
        """
        Obtiene una propiedad exclusiva específica por su código.
        
        Args:
            property_code: Código de la propiedad a buscar
            
        Returns:
            Optional[Dict]: Propiedad encontrada o None
        """
        try:
            logger.info(f"Fetching exclusive property with code: {property_code}")
            
            response = self.supabase.table('aura_properties')\
                .select('*')\
                .eq('property_code', property_code)\
                .execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Found exclusive property: {property_code}")
                return response.data[0]
            
            logger.warning(f"Exclusive property not found: {property_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting exclusive property by code: {e}")
            return None
    
    async def get_exclusive_properties_by_municipality(self, municipality: str) -> List[Dict]:
        """
        Obtiene propiedades exclusivas filtradas por municipio.
        
        Args:
            municipality: Nombre del municipio
            
        Returns:
            List[Dict]: Lista de propiedades del municipio en orden aleatorio
        """
        try:
            logger.info(f"Fetching exclusive properties for municipality: {municipality}")
            
            response = self.supabase.table('aura_properties')\
                .select('*')\
                .eq('municipality', municipality)\
                .execute()
            
            if not response.data:
                logger.warning(f"No exclusive properties found for municipality: {municipality}")
                return []
            
            # Mezclar aleatoriamente los resultados
            properties = list(response.data)
            random.shuffle(properties)
            
            logger.info(f"Retrieved {len(properties)} exclusive properties for {municipality}")
            return properties
            
        except Exception as e:
            logger.error(f"Error getting exclusive properties by municipality: {e}")
            return []
    
    async def get_exclusive_properties_by_price_range(self, min_price: float, max_price: float) -> List[Dict]:
        """
        Obtiene propiedades exclusivas filtradas por rango de precio.
        
        Args:
            min_price: Precio mínimo
            max_price: Precio máximo
            
        Returns:
            List[Dict]: Lista de propiedades en el rango de precio en orden aleatorio
        """
        try:
            logger.info(f"Fetching exclusive properties with price range: {min_price} - {max_price}")
            
            response = self.supabase.table('aura_properties')\
                .select('*')\
                .gte('price', min_price)\
                .lte('price', max_price)\
                .execute()
            
            if not response.data:
                logger.warning(f"No exclusive properties found in price range: {min_price} - {max_price}")
                return []
            
            # Mezclar aleatoriamente los resultados
            properties = list(response.data)
            random.shuffle(properties)
            
            logger.info(f"Retrieved {len(properties)} exclusive properties in price range")
            return properties
            
        except Exception as e:
            logger.error(f"Error getting exclusive properties by price range: {e}")
            return []
