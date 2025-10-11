"""
Helper común para inicialización de Supabase con patrón singleton
"""
import logging
from typing import Optional
from supabase import create_client, Client
from app.config import Config

logger = logging.getLogger(__name__)

class SupabaseSingleton:
    """Singleton para el cliente de Supabase"""
    _instance = None
    _client = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseSingleton, cls).__new__(cls)
        return cls._instance
    
    def get_client(self) -> Optional[Client]:
        """
        Obtiene el cliente de Supabase (singleton)
        
        Returns:
            Client de Supabase o None si hay error
        """
        if not self._initialized:
            self._initialize_client()
        
        return self._client
    
    def _initialize_client(self):
        """Inicializa el cliente de Supabase una sola vez"""
        try:
            supabase_url = Config.SUPABASE_URL
            supabase_key = Config.get_supabase_key()
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not found")
                self._client = None
                self._initialized = True
                return
                
            self._client = create_client(supabase_url, supabase_key)
            
            # Verificar conexión solo una vez al inicializar
            self._client.table('conversations').select('id').limit(1).execute()
            logger.info("Supabase connection verified successfully")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing Supabase: {e}")
            self._client = None
            self._initialized = True

# Instancia global del singleton
_supabase_singleton = SupabaseSingleton()

def get_supabase_client() -> Optional[Client]:
    """
    Obtiene el cliente de Supabase usando patrón singleton
    
    Returns:
        Client de Supabase o None si hay error
    """
    return _supabase_singleton.get_client()
