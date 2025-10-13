from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union


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
    session_id: Optional[str] = Field(None, description="ID de sesión")
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
    need_finance: Optional[str] = Field(None, description="Necesidad de financiación del cliente")
    time_searching: Optional[str] = Field(None, description="Tiempo que lleva buscando el piso")
    utms: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parámetros UTM de tracking")
    
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
    need_finance: Optional[str] = Field(None, description="Necesidad de financiación del cliente")
    time_searching: Optional[str] = Field(None, description="Tiempo que lleva buscando el piso")
    utms: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parámetros UTM de tracking")
    preferences_metadata: Optional[Dict[str, Any]] = Field(None, description="Metadatos de preferencias")
    conversation_summary: Optional[str] = Field(None, description="Resumen de la conversación")
    created_at: str = Field(..., description="Fecha de creación")


class PropertySearchRequest(BaseModel):
    """Modelo de solicitud de búsqueda de propiedades por IDs"""
    property_ids: Union[str, List[str]] = Field(..., description="ID de propiedad o lista de IDs a buscar")
    
    @validator('property_ids', pre=True)
    def validate_property_ids(cls, v):
        """Valida y normaliza los property_ids"""
        if isinstance(v, str):
            # Si es un string, convertir a lista
            return [v.strip()]
        elif isinstance(v, list):
            # Si es una lista, limpiar y filtrar elementos vacíos
            return [str(item).strip() for item in v if str(item).strip()]
        else:
            raise ValueError('property_ids debe ser un string o una lista de strings')


class PropertySearchResponse(BaseModel):
    """Modelo de respuesta de búsqueda de propiedades"""
    found_properties: List[Dict[str, Any]] = Field(..., description="Propiedades encontradas")
    total_found: int = Field(..., description="Total de propiedades encontradas")
    requested_ids: List[str] = Field(..., description="IDs solicitados")
    not_found_ids: List[str] = Field(..., description="IDs no encontrados")


class PropertyDescriptionRequest(BaseModel):
    """Modelo de solicitud para obtener descripción de propiedad"""
    property_code: str = Field(..., description="Código de la propiedad a consultar")


class PropertyDescriptionResponse(BaseModel):
    """Modelo de respuesta de descripción de propiedad"""
    property_code: str = Field(..., description="Código de la propiedad")
    description: str = Field(..., description="Descripción original de la propiedad")
    description_paraphrased: Optional[str] = Field(None, description="Descripción parafraseada (si existe)")
    paraphrased: bool = Field(..., description="Indica si la descripción fue parafraseada en esta consulta")
    message: str = Field(..., description="Mensaje informativo sobre el procesamiento")


