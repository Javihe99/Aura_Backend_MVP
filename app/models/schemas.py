from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """Modelo de solicitud de chat con memoria"""
    prompt: str = Field(..., description="Mensaje del usuario")
    session_id: Optional[str] = Field(None, description="ID de sesión para memoria")
    ip_address: Optional[str] = Field(None, description="Dirección IP del usuario")
    limit: int = Field(20, description="Número máximo de propiedades a devolver", ge=1, le=200)


class MapSearchRequest(BaseModel):
    """Modelo de búsqueda por coordenadas"""
    lng: float = Field(..., description="Longitud")
    lat: float = Field(..., description="Latitud")
    limit: int = Field(20, description="Número máximo de propiedades", ge=1, le=200)
    metro: int = Field(1000, description="Radio en metros", ge=100, le=5000)
    session_id: Optional[str] = Field(None, description="ID de sesión")
    ip_address: Optional[str] = Field(None, description="Dirección IP del usuario")


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


class AppointmentRequest(BaseModel):
    """Modelo de solicitud de cita"""
    session_id: str = Field(..., description="ID de sesión del usuario")
    appointment_time: str = Field(..., description="Fecha y hora de la cita (ISO format)")
    email: Optional[str] = Field(None, description="Email del cliente")
    name: str = Field(..., description="Nombre del cliente")
    phone: Optional[str] = Field(None, description="Teléfono del cliente")
    property_id: Optional[str] = Field(None, description="ID de propiedad específica")
    property_url: Optional[str] = Field(None, description="URL de propiedad específica")
    
    @validator('phone', always=True)
    def validate_contact_info(cls, v, values):
        """Valida que al menos email o teléfono esté presente"""
        email = values.get('email')
        phone = v
        
        # Si no hay email ni teléfono, lanzar error
        if not email and not phone:
            raise ValueError('Al menos uno de email o teléfono debe ser proporcionado para contactar al cliente')
        
        return v


class AppointmentResponse(BaseModel):
    """Modelo de respuesta de cita"""
    appointment_id: str = Field(..., description="ID de la cita creada")
    session_id: str = Field(..., description="ID de sesión")
    appointment_time: str = Field(..., description="Fecha y hora de la cita")
    email: Optional[str] = Field(..., description="Email del cliente")
    name: str = Field(..., description="Nombre del cliente")
    phone: Optional[str] = Field(..., description="Teléfono del cliente")
    property_id: Optional[str] = Field(None, description="ID de propiedad específica")
    property_url: Optional[str] = Field(None, description="URL de propiedad específica")
    user_location: Optional[str] = Field(None, description="Ubicación detectada por IP")
    budget_min: Optional[int] = Field(None, description="Presupuesto mínimo detectado")
    budget_max: Optional[int] = Field(None, description="Presupuesto máximo detectado")
    financing: bool = Field(False, description="Necesita financiación")
    preferences_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadatos de preferencias")
    conversation_summary: Optional[str] = Field(None, description="Resumen de la conversación")
    created_at: str = Field(..., description="Fecha de creación")


