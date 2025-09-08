from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Modelo de solicitud de chat con memoria"""
    prompt: str = Field(..., description="Mensaje del usuario")
    session_id: Optional[str] = Field(None, description="ID de sesión para memoria")
    user_id: Optional[str] = Field(None, description="ID de usuario")
    limit: int = Field(20, description="Número máximo de propiedades a devolver", ge=1, le=200)


class MapSearchRequest(BaseModel):
    """Modelo de búsqueda por coordenadas"""
    lng: float = Field(..., description="Longitud")
    lat: float = Field(..., description="Latitud")
    limit: int = Field(20, description="Número máximo de propiedades", ge=1, le=200)
    metro: int = Field(1000, description="Radio en metros", ge=100, le=5000)
    session_id: Optional[str] = Field(None, description="ID de sesión")


class ChatResponse(BaseModel):
    """Modelo de respuesta del chat"""
    llm_summary: str = Field(..., description="Resumen generado por LLM")
    properties: List[Dict[str, Any]] = Field(..., description="Lista de propiedades")
    total_found: int = Field(..., description="Total de propiedades encontradas")
    session_id: str = Field(..., description="ID de sesión")
    search_params: Dict[str, Any] = Field(..., description="Parámetros de búsqueda utilizados")


class ConversationHistoryResponse(BaseModel):
    """Modelo de respuesta del historial de conversación"""
    session_id: str = Field(..., description="ID de sesión")
    history: List[Dict[str, Any]] = Field(..., description="Historial de mensajes")
    message_count: int = Field(..., description="Número total de mensajes")


class HealthResponse(BaseModel):
    """Modelo de respuesta del health check"""
    status: str = Field(..., description="Estado del servicio")
    timestamp: str = Field(..., description="Timestamp del check")
    supabase_connected: bool = Field(..., description="Estado de conexión con Supabase")


