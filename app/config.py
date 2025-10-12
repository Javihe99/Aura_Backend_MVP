import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
class Config:
    """Configuración centralizada de la aplicación"""
    
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_PRIVATE_KEY: Optional[str] = os.getenv("SUPABASE_PRIVATE_KEY")
    
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))
    
    MIN_QUALITY_THRESHOLD: float = float(os.getenv("MIN_QUALITY_THRESHOLD", "0.3"))
    FALLBACK_QUALITY_THRESHOLD: float = float(os.getenv("FALLBACK_QUALITY_THRESHOLD", "0.2"))
    
    DEFAULT_CITY: str = os.getenv("DEFAULT_CITY", "Madrid, España")
    DEFAULT_SEARCH_LIMIT: int = int(os.getenv("DEFAULT_SEARCH_LIMIT", "20"))
    DEFAULT_SEARCH_RADIUS: int = int(os.getenv("DEFAULT_SEARCH_RADIUS", "1000"))
    
    @classmethod
    def get_supabase_status(cls) -> str:
        """Obtiene el estado de la configuración de Supabase"""
        if cls.SUPABASE_URL and cls.SUPABASE_PRIVATE_KEY:
            return "configured"
        elif cls.SUPABASE_URL and not cls.SUPABASE_PRIVATE_KEY:
            return "partially_configured"
        else:
            return "not_configured"
    
    @classmethod
    def get_supabase_key(cls) -> Optional[str]:
        """Obtiene la clave privada de Supabase"""
        return cls.SUPABASE_PRIVATE_KEY
    
    @classmethod
    def print_config(cls):
        """Imprime la configuración actual"""
        print("Aura Backend MVP Configuration:")
        print(f"   Server: {cls.HOST}:{cls.PORT}")
        print(f"   OpenAI API: {'OK' if cls.OPENAI_API_KEY else 'NOT SET'}")
        print(f"   Google API: {'OK' if cls.GOOGLE_API_KEY else 'NOT SET'}")
        print(f"   Supabase: {cls.get_supabase_status()}")
        print(f"   Log Level: {cls.LOG_LEVEL}")
        print(f"   Max Concurrent: {cls.MAX_CONCURRENT_REQUESTS}")
        print(f"   Rate Limit: {cls.RATE_LIMIT_PER_MINUTE}/min")


config = Config()

