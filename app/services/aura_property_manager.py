import logging
import random
from typing import List, Dict, Optional
from app.services.supabase_helper import get_supabase_client

logger = logging.getLogger(__name__)


class AuraPropertyManager:
    """Gestor de propiedades exclusivas de Aura"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        if not self.supabase:
            raise Exception("Supabase credentials not configured")
    
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