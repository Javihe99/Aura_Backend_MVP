import logging
from contextlib import asynccontextmanager
from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Importar modelos
from app.models.schemas import (
    ChatRequest, MapSearchRequest, ChatResponse,
    ConversationHistoryResponse, HealthResponse
)
from app.services.ai_parse import get_llm_result, validate_and_correct_location
from app.services.concurrency_manager import RequestLimiter, AsyncTaskManager
# Importar servicios
from app.services.memory_manager import ConversationMemory
from app.services.property_manager import PropertyManager
from app.services.property_summarizer import PropertySummarizer
from app.services.quality_filter import PropertyQualityFilter
# Importar utilidades existentes
from idealista_hook import IdealistaHook
from utils import get_area_by_giving_location, to_idealista_multipolygon, create_meter_radius_circle

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración por defecto
DEFAULT_CITY = 'Madrid, España'


# ========== HELPER FUNCTIONS ==========
def get_idealista_properties(prompt_result: dict) -> pd.DataFrame:
    """Obtiene propiedades de Idealista usando los parámetros proporcionados"""
    sort_parse = {
        # Defecto es 0
        # Otros estados = 1
        "Alquilada": 2,
        "Nuda propiedad": 3,
        "Ocupada ilegalmente": 4,
    }
    property = IdealistaHook()
    property.update_token()
    status, dict = property.search_properties_by_coordinates(**prompt_result)
    if status is False:
        raise ValueError(dict)
    df = pd.json_normalize(dict['elementList'])
    df[['additional_info_tag', 'additional_info_name']] = df['labels'].apply(
        lambda x: pd.Series([x[0]['name'], x[0]['text']]) if isinstance(x, list) else pd.Series([None, None]))
    df['status_sort'] = np.where(df['additional_info_name'].isna(), 0,
                                 df['additional_info_name'].map(sort_parse).fillna(1)).astype(int)
    df = df.sort_values(by=['status_sort', 'priceByArea'], ascending=True)
    logger.info(f"Se han encontrado un total de {len(df)} propiedades")
    df = df.replace({np.nan: None})
    return df


# ========== LIFECYCLE MANAGER ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor del ciclo de vida de la aplicación"""
    # Startup
    logger.info("🚀 Starting Aura Backend MVP...")

    # Inicializar componentes
    app.state.memory_manager = ConversationMemory()
    app.state.property_manager = PropertyManager()
    app.state.quality_filter = PropertyQualityFilter()
    app.state.summarizer = PropertySummarizer()
    app.state.request_limiter = RequestLimiter(max_concurrent=10, rate_limit_per_minute=100)
    app.state.task_manager = AsyncTaskManager()

    logger.info("✅ All services initialized successfully")

    yield

    # Shutdown
    logger.info("🛑 Shutting down Aura Backend MVP...")

    # Limpiar tareas activas
    for task_id in list(app.state.task_manager.tasks.keys()):
        await app.state.task_manager.cancel_task(task_id)

    # Limpiar solicitudes antiguas
    await app.state.request_limiter.cleanup_old_requests()

    logger.info("✅ Cleanup completed")


# ========== FASTAPI APP ==========
app = FastAPI(
    title="Aura Backend MVP",
    description="""
    ## 🏠 Backend API para búsqueda inteligente de propiedades inmobiliarias
    
    ### ✨ Características principales:
    - 🤖 **Búsqueda por lenguaje natural** con LLM (OpenAI/Gemini)
    - 🗺️ **Búsqueda por coordenadas** geográficas
    - 💾 **Memoria de conversación** persistente con Supabase
    - 🎯 **Filtros de calidad inteligentes** para mejores resultados
    - 📊 **Resúmenes automáticos** generados por LLM
    - ⚡ **Gestión de concurrencia** y rate limiting
    - 🔄 **Historial de conversaciones** por sesión/usuario
    
    ### 🚀 Endpoints disponibles:
    - `POST /chat`: Búsqueda por lenguaje natural con memoria
    - `POST /maps`: Búsqueda por coordenadas geográficas
    - `GET /conversation/{session_id}`: Obtener historial de conversación
    - `GET /health`: Estado del servicio y conexiones
    
    ### 📝 Ejemplos de uso:
    ```json
    {
      "prompt": "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000€",
      "session_id": "user_123",
      "ip_address": "192.168.1.1",
      "limit": 20
    }
    ```
    
    ### 🔧 Configuración:
    - **SUPABASE_URL**: URL de tu proyecto Supabase
    - **SUPABASE_ANON_KEY**: Clave anónima de Supabase
    - **OPENAI_API_KEY**: Clave de API de OpenAI
    - **GOOGLE_API_KEY**: Clave de API de Google (Gemini)
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== ENDPOINTS ==========
@app.get("/", tags=["General"])
async def root():
    """Endpoint raíz con información del servicio"""
    return {
        "message": "🏠 Bienvenido al Backend MVP de Aura",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "ok",
        "features": [
            "Búsqueda inteligente por LLM",
            "Memoria de conversación",
            "Filtros de calidad",
            "Gestión de concurrencia"
        ]
    }


@app.post("/chat", response_model=ChatResponse, tags=["Search"])
async def chat_search(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    🔍 Búsqueda de propiedades mediante lenguaje natural con memoria.
    
    Este endpoint procesa consultas en lenguaje natural, las interpreta usando LLM,
    mantiene el historial de conversación, y devuelve propiedades relevantes 
    con un resumen generado automáticamente.
    
    ### 📝 Ejemplos de consultas:
    - "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000€"
    - "Busco casa con jardín en las afueras de Madrid"
    - "Apartamento céntrico con terraza y ascensor en Vigo"
    - "Necesito algo más barato que lo anterior"
    """
    # Obtener o crear sesión
    session_id = await app.state.memory_manager.get_or_create_session(
        request.session_id, request.ip_address
    )

    # Verificar límite de concurrencia
    try:
        await app.state.request_limiter.acquire(session_id)
    except HTTPException as e:
        raise e

    try:
        # Obtener historial de conversación
        history = await app.state.memory_manager.get_conversation_history(session_id)
        conversation_context = app.state.memory_manager.format_history_for_llm(history)

        # Guardar mensaje del usuario
        background_tasks.add_task(
            app.state.memory_manager.save_message,
            session_id, "user", request.prompt, None, request.ip_address
        )

        # Procesar con LLM incluyendo contexto
        enhanced_prompt = f"{conversation_context}\n\nNueva consulta: {request.prompt}"
        prompt_result = get_llm_result(enhanced_prompt)

        # Validar y corregir ubicación
        location_validation = {}
        if "locationName" in prompt_result:
            location_validation = validate_and_correct_location(
                prompt_result["locationName"],
                DEFAULT_CITY
            )

            if location_validation["confidence"] > 0.7:
                logger.info(f"Using corrected location: {location_validation['corrected_location']}")
            else:
                logger.warning(f"Low confidence location: {location_validation['reason']}")
        else:
            raise ValueError("No se especificó ubicación en la consulta")

        # Obtener coordenadas y crear polígono
        if location_validation:
            coordinates = get_area_by_giving_location(location_validation["corrected_location"])
        else:
            coordinates = get_area_by_giving_location(DEFAULT_CITY)

        geojson_str = to_idealista_multipolygon(coordinates)
        prompt_result['shape'] = geojson_str

        # Obtener propiedades
        df = get_idealista_properties(prompt_result)

        # Aplicar filtros de calidad
        if not df.empty:
            df = app.state.quality_filter.filter_and_rank_properties(df, top_n=request.limit * 2)

        # Limitar resultados y convertir a lista de diccionarios
        records = df.head(request.limit).to_dict(orient='records')

        # Generar resumen con LLM
        summary = await app.state.summarizer.generate_summary(records, conversation_context=conversation_context)

        # Valor un pesado eliminar 'shape' del prompt_result antes de guardarlo
        del prompt_result['shape']

        # Guardar propiedades en la base de datos (por separado)
        background_tasks.add_task(
            app.state.property_manager.save_properties,
            records
        )

        # Guardar conversación del asistente (por separado)
        # Extraer property_list usando pandas (más eficiente)
        property_list = df['propertycode'].tolist() if not df.empty else []
        
        background_tasks.add_task(
            app.state.memory_manager.save_message,
            session_id, "assistant", summary,
            {"properties_found": len(records), "search_params": prompt_result,
             "property_list": property_list,
             "llm_summary": summary}, request.ip_address
        )

        return ChatResponse(
            llm_summary=summary,
            properties=records,
            total_found=len(df),
            session_id=session_id,
            search_params=prompt_result
        )

    except Exception as e:
        logger.error(f"Error in chat_search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        app.state.request_limiter.release(session_id)


@app.post("/maps", response_model=ChatResponse, tags=["Search"])
async def maps_search(request: MapSearchRequest, background_tasks: BackgroundTasks):
    """
    🗺️ Búsqueda de propiedades por coordenadas geográficas.
    
    Busca propiedades en un radio específico alrededor de las coordenadas proporcionadas,
    aplicando filtros de calidad y generando resúmenes automáticos.
    """
    # Obtener o crear sesión
    session_id = await app.state.memory_manager.get_or_create_session(
        request.session_id, request.ip_address
    )

    try:
        await app.state.request_limiter.acquire(session_id)
    except HTTPException as e:
        raise e

    try:
        # Crear círculo de búsqueda
        circle = create_meter_radius_circle(request.lat, request.lng, request.metro)
        multipolygon_str = to_idealista_multipolygon(circle)

        prompt_result_final = {'shape': multipolygon_str}

        # Obtener propiedades
        df = get_idealista_properties(prompt_result_final)

        # Aplicar filtros de calidad
        if not df.empty:
            df = app.state.quality_filter.filter_and_rank_properties(df, top_n=request.limit * 2)

        records = df.head(request.limit).to_dict(orient='records')

        # Generar resumen
        search_description = f"Búsqueda en radio de {request.metro}m desde coordenadas ({request.lat}, {request.lng})"
        summary = await app.state.summarizer.generate_summary(
            records,
            {"lat": request.lat, "lng": request.lng, "radius": request.metro},
            search_description
        )

        # Guardar propiedades en la base de datos (por separado)
        background_tasks.add_task(
            app.state.property_manager.save_properties,
            records
        )

        # Guardar conversación en historial (por separado)
        # Extraer property_list usando pandas (más eficiente)
        property_list = df['propertycode'].tolist() if not df.empty else []
        
        background_tasks.add_task(
            app.state.memory_manager.save_message,
            session_id, "system", search_description,
            {"lat": request.lat, "lng": request.lng, "radius": request.metro, 
             "properties_found": len(records), "property_list": property_list}, request.ip_address
        )

        return ChatResponse(
            llm_summary=summary,
            properties=records,
            total_found=len(df),
            session_id=session_id,
            search_params={"lat": request.lat, "lng": request.lng, "radius": request.metro}
        )

    except Exception as e:
        logger.error(f"Error in maps_search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        app.state.request_limiter.release(session_id)


@app.get("/conversation/{session_id}", response_model=ConversationHistoryResponse, tags=["Memory"])
async def get_conversation_history(session_id: str):
    """
    💾 Obtiene el historial de conversación de una sesión específica.
    
    Permite recuperar el contexto completo de una conversación para mantener
    la continuidad en las búsquedas de propiedades.
    """
    history = await app.state.memory_manager.get_conversation_history(session_id)
    return ConversationHistoryResponse(
        session_id=session_id,
        history=history,
        message_count=len(history)
    )


@app.get("/properties/{session_id}", tags=["Properties"])
async def get_properties_by_session(session_id: str):
    """
    🏠 Obtiene todas las propiedades relacionadas con una sesión específica.
    
    Devuelve todas las propiedades que han sido mostradas en las conversaciones
    de la sesión especificada.
    """
    properties = await app.state.property_manager.get_properties_by_session(session_id)
    return {
        "session_id": session_id,
        "properties": properties,
        "total_properties": len(properties)
    }


@app.get("/property/{property_code}", tags=["Properties"])
async def get_property_by_code(property_code: str):
    """
    🏠 Obtiene una propiedad específica por su código.
    
    Devuelve todos los detalles de una propiedad específica.
    """
    property_data = await app.state.property_manager.get_property_by_code(property_code)
    if not property_data:
        raise HTTPException(status_code=404, detail="Property not found")
    
    return property_data


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """🏥 Endpoint de health check con estado de conexiones"""
    supabase_connected = app.state.memory_manager.supabase is not None

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        supabase_connected=supabase_connected
    )


@app.get("/stats", tags=["General"])
async def get_service_stats():
    """📊 Obtiene estadísticas del servicio"""
    return {
        "active_requests": app.state.request_limiter.get_active_requests_count(),
        "active_tasks": len(app.state.task_manager.tasks),
        "timestamp": datetime.now().isoformat()
    }


# ========== LEGACY ENDPOINTS (Mantenidos para compatibilidad) ==========
@app.post("/new_prompt", tags=["Legacy"])
async def new_prompt_legacy(request: dict):
    """
    ⚠️ Endpoint legacy mantenido para compatibilidad.
    
    Se recomienda usar `/chat` para nuevas implementaciones.
    """
    logger.warning("Using legacy endpoint /new_prompt. Consider migrating to /chat")

    # Convertir request legacy a nuevo formato
    chat_request = ChatRequest(
        prompt=request.get("prompt", ""),
        limit=int(request.get("limit", 200)),
        session_id=request.get("session_id"),
        ip_address=request.get("ip_address")
    )

    # Usar el nuevo endpoint
    return await chat_search(chat_request, BackgroundTasks())


@app.post("/new_maps", tags=["Legacy"])
async def new_maps_legacy(request: dict):
    """
    ⚠️ Endpoint legacy mantenido para compatibilidad.
    
    Se recomienda usar `/maps` para nuevas implementaciones.
    """
    logger.warning("Using legacy endpoint /new_maps. Consider migrating to /maps")

    # Convertir request legacy a nuevo formato
    maps_request = MapSearchRequest(
        lng=float(request.get("lng", 0)),
        lat=float(request.get("lat", 0)),
        limit=int(request.get("limit", 200)),
        metro=int(request.get("metro", 1000)),
        session_id=request.get("session_id"),
        ip_address=request.get("ip_address")
    )

    # Usar el nuevo endpoint
    return await maps_search(maps_request, BackgroundTasks())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
