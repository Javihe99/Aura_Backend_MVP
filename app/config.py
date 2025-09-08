import os
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Config:
    """Configuración centralizada de la aplicación"""
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    
    # Supabase Configuration
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY: Optional[str] = os.getenv("SUPABASE_ANON_KEY")
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Concurrency Settings
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    
    # Memory Settings
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))
    
    # Quality Filter Settings
    MIN_QUALITY_THRESHOLD: float = float(os.getenv("MIN_QUALITY_THRESHOLD", "0.3"))
    FALLBACK_QUALITY_THRESHOLD: float = float(os.getenv("FALLBACK_QUALITY_THRESHOLD", "0.2"))
    
    # Default Values
    DEFAULT_CITY: str = os.getenv("DEFAULT_CITY", "Madrid, España")
    DEFAULT_SEARCH_LIMIT: int = int(os.getenv("DEFAULT_SEARCH_LIMIT", "20"))
    DEFAULT_SEARCH_RADIUS: int = int(os.getenv("DEFAULT_SEARCH_RADIUS", "1000"))
    
    @classmethod
    def validate(cls) -> bool:
        """Valida que las configuraciones requeridas estén presentes"""
        required_keys = ["OPENAI_API_KEY", "GOOGLE_API_KEY"]
        missing_keys = [key for key in required_keys if not getattr(cls, key)]
        
        if missing_keys:
            print(f"⚠️  Warning: Missing required API keys: {', '.join(missing_keys)}")
            print("   Some features may not work properly.")
            return False
        
        return True
    
    @classmethod
    def get_supabase_status(cls) -> str:
        """Obtiene el estado de la configuración de Supabase"""
        if cls.SUPABASE_URL and cls.SUPABASE_ANON_KEY:
            return "configured"
        elif cls.SUPABASE_URL or cls.SUPABASE_ANON_KEY:
            return "partially_configured"
        else:
            return "not_configured"
    
    @classmethod
    def print_config(cls):
        """Imprime la configuración actual"""
        print("🔧 Aura Backend MVP Configuration:")
        print(f"   Server: {cls.HOST}:{cls.PORT}")
        print(f"   OpenAI API: {'✅' if cls.OPENAI_API_KEY else '❌'}")
        print(f"   Google API: {'✅' if cls.GOOGLE_API_KEY else '❌'}")
        print(f"   Supabase: {cls.get_supabase_status()}")
        print(f"   Log Level: {cls.LOG_LEVEL}")
        print(f"   Max Concurrent: {cls.MAX_CONCURRENT_REQUESTS}")
        print(f"   Rate Limit: {cls.RATE_LIMIT_PER_MINUTE}/min")

# Instancia global de configuración
config = Config()






