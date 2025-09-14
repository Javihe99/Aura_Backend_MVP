import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Union

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware

# Importar modelos
from app.models.schemas import (
    ChatRequest, MapSearchRequest, ChatResponse,
    ConversationHistoryResponse, HealthResponse,
    AppointmentRequest, AppointmentResponse
)
from app.services.ai_parse import get_llm_result, validate_and_correct_location
from app.services.concurrency_manager import RequestLimiter, AsyncTaskManager
# Importar servicios
from app.services.memory_manager import ConversationMemory
from app.services.property_manager import PropertyManager
from app.services.property_summarizer import PropertySummarizer
from app.services.quality_filter import PropertyQualityFilter
from app.services.intent_classifier import IntentClassifier, SeniorRealEstateAgent
from app.services.appointment_manager import AppointmentManager
from app.services.appointment_analyzer import AppointmentAnalyzer
from app.services.email_service import EmailService
# Importar utilidades existentes
from idealista_hook import IdealistaHook
from utils import get_area_by_giving_location, to_idealista_multipolygon, create_meter_radius_circle

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración por defecto
DEFAULT_CITY = 'Madrid, España'


# ========== HELPER FUNCTIONS ==========
def generate_search_suggestions(prompt_result: dict) -> str:
    """Genera sugerencias para el usuario cuando no se encuentran propiedades"""
    suggestions = []
    
    # Sugerencias basadas en los parámetros de búsqueda
    if prompt_result.get('maxPrice'):
        suggestions.append(f"• Aumentar el presupuesto máximo (actual: {prompt_result['maxPrice']:,}€)")
    
    if prompt_result.get('minRooms'):
        suggestions.append(f"• Reducir el número mínimo de habitaciones (actual: {prompt_result['minRooms']})")
    
    if prompt_result.get('minSize'):
        suggestions.append(f"• Reducir los metros cuadrados mínimos (actual: {prompt_result['minSize']}m²)")
    
    if prompt_result.get('locationName'):
        suggestions.append(f"• Ampliar la zona de búsqueda alrededor de {prompt_result['locationName']}")
    
    # Sugerencias generales
    suggestions.extend([
        "• Considerar propiedades en zonas cercanas",
        "• Revisar si hay propiedades similares con características ligeramente diferentes",
        "• Contactar con un agente inmobiliario para búsquedas personalizadas"
    ])
    
    return "Te sugiero:\n" + "\n".join(suggestions[:4])  # Limitar a 4 sugerencias


def get_idealista_properties(prompt_result: dict) -> (pd.DataFrame,dict):
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
    status, records = property.search_properties_by_coordinates(**prompt_result)
    if status is False:
        raise ValueError(records)
    
    # Verificar si hay propiedades encontradas
    if not records.get('elementList') or len(records['elementList']) == 0:
        logger.warning("No se encontraron propiedades con los parámetros especificados")
        # Crear DataFrame vacío con las columnas esperadas
        empty_df = pd.DataFrame(columns=['propertyCode', 'labels', 'priceByArea'])
        empty_df = empty_df.replace({np.nan: None})
        del records['elementList']
        return empty_df, records
    
    df = pd.json_normalize(records['elementList'])
    
    # Verificar si la columna 'labels' existe antes de procesarla
    if 'labels' in df.columns:
        df[['additional_info_tag', 'additional_info_name']] = df['labels'].apply(
            lambda x: pd.Series([x[0]['name'], x[0]['text']]) if isinstance(x, list) and len(x) > 0 else pd.Series([None, None]))
    else:
        # Si no hay columna labels, crear columnas vacías
        df['additional_info_tag'] = None
        df['additional_info_name'] = None
    
    df['status_sort'] = np.where(df['additional_info_name'].isna(), 0,
                                 df['additional_info_name'].map(sort_parse).fillna(1)).astype(int)
    df = df.sort_values(by=['status_sort', 'priceByArea'], ascending=True)
    logger.info(f"Se han encontrado un total de {len(df)} propiedades")
    df = df.replace({np.nan: None})
    del records['elementList']
    return df, records


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
    app.state.intent_classifier = IntentClassifier()
    app.state.senior_agent = SeniorRealEstateAgent()
    app.state.appointment_manager = AppointmentManager()
    app.state.appointment_analyzer = AppointmentAnalyzer()
    app.state.email_service = EmailService()
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
    ## 🏠 Backend API para asistencia inmobiliaria inteligente
    
    ### ✨ Características principales:
    - 🧠 **Clasificación inteligente de intenciones** usando IA
    - 🏠 **Búsqueda de propiedades** por lenguaje natural con LLM (OpenAI/Gemini)
    - 👨‍💼 **Asesor experto** para consultas generales del sector inmobiliario
    - 🗺️ **Búsqueda por coordenadas** geográficas
    - 💾 **Memoria de conversación** persistente con Supabase
    - 🎯 **Filtros de calidad inteligentes** para mejores resultados
    - 📊 **Resúmenes automáticos** generados por LLM
    - ⚡ **Gestión de concurrencia** y rate limiting
    - 🔄 **Historial de conversaciones** por sesión/usuario
    
    ### 🚀 Endpoints disponibles:
    - `POST /chat`: Chat inteligente con clasificación de intenciones
    - `POST /maps`: Búsqueda por coordenadas geográficas
    - `POST /appointment`: Crear cita inmobiliaria con análisis IA
    - `GET /conversation/{session_id}`: Obtener historial de conversación
    - `GET /appointments/{session_id}`: Obtener citas de una sesión
    - `GET /appointment/{appointment_id}`: Obtener cita específica
    - `GET /appointments/recent`: Obtener citas recientes
    - `GET /health`: Estado del servicio y conexiones
    
    ### 📝 Ejemplos de uso:
    
    **Búsqueda de propiedades:**
    ```json
    {
      "prompt": "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000€",
      "session_id": "user_123",
      "ip_address": "192.168.1.1",
      "limit": 20
    }
    ```
    
    **Consulta general:**
    ```json
    {
      "prompt": "¿Cómo funciona el proceso de compra de una vivienda?",
      "session_id": "user_123",
      "ip_address": "192.168.1.1",
      "limit": 20
    }
    ```
    
    **Crear cita inmobiliaria:**
    ```json
    {
      "session_id": "user_123",
      "appointment_time": "2024-01-15T10:30:00Z",
      "email": "cliente@ejemplo.com",
      "name": "Juan Pérez",
      "phone": "+34123456789",
      "property_id": "12345",
      "property_url": "https://www.idealista.com/inmueble/12345",
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
            "Clasificación inteligente de intenciones",
            "Búsqueda inteligente por LLM",
            "Asesor experto inmobiliario",
            "Memoria de conversación",
            "Filtros de calidad",
            "Gestión de concurrencia",
            "Sistema de citas con análisis IA",
            "Notificaciones por email"
        ]
    }


@app.post("/chat", response_model=ChatResponse, tags=["Search"])
async def chat_search(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    🔍 Chat inteligente con clasificación de intenciones y memoria.
    
    Este endpoint procesa consultas en lenguaje natural con un sistema inteligente que:
    1. **Clasifica la intención** del usuario usando IA
    2. **Si busca propiedades**: Procesa la búsqueda con LLM y devuelve resultados
    3. **Si es consulta general**: Responde como un senior de inmobiliaria experto
    4. **Mantiene memoria** de la conversación para contexto continuo
    
    ### 🏠 Búsquedas de propiedades (ejemplos):
    - "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000€"
    - "Busco casa con jardín en las afueras de Madrid"
    - "Apartamento céntrico con terraza y ascensor en Vigo"
    - "Necesito algo más barato que lo anterior"
    
    ### 💼 Consultas generales (ejemplos):
    - "¿Cómo funciona el proceso de compra de una vivienda?"
    - "¿Qué documentación necesito para vender mi casa?"
    - "¿Cuáles son las mejores zonas para invertir en Madrid?"
    - "¿Qué impuestos debo pagar al comprar un piso?"
    - "¿Cuál es la diferencia entre compra y alquiler?"
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

        # 1. CLASIFICAR INTENCIÓN DEL USUARIO
        intent_classification = await app.state.intent_classifier.classify_intent(
            request.prompt, conversation_context
        )
        
        logger.info(f"Intent classification: {intent_classification}")
        
        # 2. SI NO ES BÚSQUEDA DE PROPIEDADES, RESPONDER COMO SENIOR DE INMOBILIARIA
        if intent_classification["intent"] == "general_inquiry":
            senior_response = await app.state.senior_agent.generate_response(
                request.prompt, conversation_context
            )
            
            # Guardar respuesta del senior
            background_tasks.add_task(
                app.state.memory_manager.save_message,
                session_id, "assistant", senior_response,
                {"intent": "general_inquiry", "classification": intent_classification}, 
                request.ip_address
            )
            
            return ChatResponse(
                llm_summary=senior_response,
                properties=[],
                total_found=0,
                session_id=session_id,
                search_params={"intent": "general_inquiry", "classification": intent_classification}
            )

        # 3. SI ES BÚSQUEDA DE PROPIEDADES, CONTINUAR CON EL FLUJO HABITUAL
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
        df_raw, records_raw = get_idealista_properties(prompt_result)

        # Verificar si se encontraron propiedades
        if df_raw.empty:
            # Generar mensaje de sugerencias para el usuario
            suggestions = generate_search_suggestions(prompt_result)
            no_properties_message = f"No se encontraron propiedades con los criterios especificados. {suggestions}"
            
            # Guardar mensaje del asistente
            background_tasks.add_task(
                app.state.memory_manager.save_message,
                session_id, "assistant", no_properties_message,
                {"properties_found": 0, "search_params": prompt_result,
                 "property_list": [], "llm_summary": no_properties_message}, request.ip_address
            )
            
            return ChatResponse(
                llm_summary=no_properties_message,
                properties=[],
                total_found=0,
                session_id=session_id,
                search_params=prompt_result
            )

        # Aplicar filtros de calidad
        df = app.state.quality_filter.filter_and_rank_properties(df_raw, top_n=request.limit * 3)

        # Limitar resultados y convertir a lista de diccionarios
        records = df.head(request.limit).to_dict(orient='records')

        # Generar resumen con LLM
        summary = await app.state.summarizer.generate_summary(records, conversation_context=enhanced_prompt,total_properties=records_raw.get('total', 0))

        # Valor un pesado eliminar 'shape' del prompt_result antes de guardarlo
        del prompt_result['shape']

        # Guardar propiedades en la base de datos (por separado)
        background_tasks.add_task(
            app.state.property_manager.save_properties,
            records
        )

        # Guardar conversación del asistente (por separado)
        # Extraer property_list usando pandas (más eficiente)
        property_list = df['propertyCode'].tolist() if not df.empty else []
        
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
        df_raw, records_raw = get_idealista_properties(prompt_result_final)

        # Verificar si se encontraron propiedades
        if df_raw.empty:
            # Generar mensaje de sugerencias para el usuario
            suggestions = f"• Ampliar el radio de búsqueda (actual: {request.metro}m)\n• Considerar coordenadas cercanas\n• Revisar si hay propiedades en zonas adyacentes"
            no_properties_message = f"No se encontraron propiedades en el radio de {request.metro}m desde las coordenadas especificadas. {suggestions}"
            
            # Guardar mensaje del sistema
            background_tasks.add_task(
                app.state.memory_manager.save_message,
                session_id, "system", no_properties_message,
                {"lat": request.lat, "lng": request.lng, "radius": request.metro, 
                 "properties_found": 0, "property_list": []}, request.ip_address
            )
            
            return ChatResponse(
                llm_summary=no_properties_message,
                properties=[],
                total_found=0,
                session_id=session_id,
                search_params={"lat": request.lat, "lng": request.lng, "radius": request.metro}
            )

        # Aplicar filtros de calidad
        df = app.state.quality_filter.filter_and_rank_properties(df_raw, top_n=int(request.limit * 2))

        records = df.head(int(request.limit)).to_dict(orient='records')

        # Generar resumen
        search_description = f"Búsqueda en radio de {request.metro}m desde coordenadas ({request.lat}, {request.lng})"
        summary = await app.state.summarizer.generate_summary(
            records,
            first_top_properties=20,
            conversation_context=search_description,
            total_properties=len(df)
        )

        # Guardar propiedades en la base de datos (por separado)
        background_tasks.add_task(
            app.state.property_manager.save_properties,
            records
        )

        # Guardar conversación en historial (por separado)
        # Extraer property_list usando pandas (más eficiente)
        property_list = df['propertyCode'].tolist() if not df.empty else []
        
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


@app.post("/appointment", response_model=AppointmentResponse, tags=["Appointments"])
async def create_appointment(request: AppointmentRequest, http_request: Request, background_tasks: BackgroundTasks):
    """
    📅 Crea una nueva cita inmobiliaria.
    
    Este endpoint:
    1. **Analiza el historial de conversación** del usuario usando IA
    2. **Extrae información relevante**: presupuesto, ubicación, financiación, preferencias
    3. **Detecta la ubicación** del usuario basada en su IP
    4. **Guarda la cita** en la base de datos
    5. **Envía notificación por email** con toda la información extraída
    
    ### 📋 Parámetros requeridos:
    - `session_id`: ID de sesión del usuario
    - `appointment_time`: Fecha y hora de la cita (formato ISO)
    - `email`: Email del cliente (opcional)
    - `phone`: Teléfono del cliente (opcional)
    - `name`: Nombre del cliente
    - `property_id`: ID de propiedad específica (opcional)
    - `property_url`: URL de la propiedad (opcional)
    
    ### 🔍 Información extraída automáticamente:
    - Presupuesto mínimo y máximo
    - Ubicación de interés
    - Necesidad de financiación
    - Características de la propiedad deseada
    - Contexto personal del cliente
    - Resumen de la conversación
    
    ### 📧 Notificación:
    Se envía un email detallado con toda la información.
    """



    try:
        # Validaciones (ya manejadas por el schema con validators)
        
        # Generar URL de propiedad si no se proporciona
        if request.property_id and not request.property_url:
            property_url = f"https://www.idealista.com/inmueble/{request.property_id}/"
        else:
            property_url = request.property_url
        # Obtener IP del cliente
        client_ip = http_request.client.host if http_request.client else "unknown"
        
        # Verificar límite de concurrencia
        try:
            await app.state.request_limiter.acquire(request.session_id)
        except HTTPException as e:
            raise e
        
        try:
            # 1. OBTENER HISTORIAL DE CONVERSACIÓN
            logger.info(f"Obteniendo historial para sesión: {request.session_id}")
            app.state.memory_manager.max_history = 20  # Aumentar límite para análisis de citas
            conversation_history = await app.state.memory_manager.get_conversation_history(request.session_id)
            
            # 2. ANALIZAR CONVERSACIÓN CON IA
            logger.info("Analizando conversación con IA...")
            analysis_result = await app.state.appointment_analyzer.analyze_conversation_history(
                conversation_history, client_ip
            )
            
            # 3. CREAR RESUMEN DE CONVERSACIÓN
            conversation_summary = app.state.appointment_analyzer.create_conversation_summary(
                conversation_history, analysis_result
            )
            
            # 5. PREPARAR DATOS DEL APPOINTMENT
            appointment_data = {
                "session_id": request.session_id,
                "appointment_time": request.appointment_time,
                "email": request.email,
                "phone": request.phone,
                "name": request.name,
                "property_id": request.property_id,
                "property_url": property_url,
                "user_ip": client_ip,
                "user_location": analysis_result.get("location"),
                "budget_min": analysis_result.get("budget_min"),
                "budget_max": analysis_result.get("budget_max"),
                "financing": analysis_result.get("financing", False),
                "preferences_metadata": {
                    "property_type": analysis_result.get("property_type"),
                    "bedrooms": analysis_result.get("bedrooms"),
                    "special_features": analysis_result.get("special_features", []),
                    "personal_context": analysis_result.get("personal_context"),
                    "urgency": analysis_result.get("urgency"),
                    "preferences_summary": analysis_result.get("preferences_summary")
                },
                "conversation_summary": conversation_summary
            }
            
            # 6. GUARDAR APPOINTMENT EN BASE DE DATOS
            logger.info("Guardando appointment en base de datos...")
            created_appointment = await app.state.appointment_manager.create_appointment(appointment_data)
            
            # 7. FORMATEAR RESPUESTA (una sola vez)
            response_data = app.state.appointment_manager.format_appointment_for_response(created_appointment)
            
            # 8. ENVIAR EMAIL DE NOTIFICACIÓN (en background)
            logger.info("Programando envío de email...")
            background_tasks.add_task(
                app.state.email_service.send_appointment_notification,
                response_data
            )
            
            logger.info(f"Appointment creado exitosamente: {created_appointment['id']}")
            
            return AppointmentResponse(**response_data)
            
        except Exception as e:
            logger.error(f"Error creando appointment: {str(e)}")
            # Si es un error de validación de datos, devolver 422
            if "null value" in str(e) or "constraint" in str(e):
                raise HTTPException(status_code=422, detail=f"Error de validación: {str(e)}")
            else:
                raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
        
        finally:
            app.state.request_limiter.release(request.session_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en create_appointment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/appointments/{session_id}", tags=["Appointments"])
async def get_appointments_by_session(session_id: str):
    """
    📅 Obtiene todas las citas de una sesión específica.
    
    Devuelve todas las citas programadas para la sesión especificada,
    ordenadas por fecha de creación (más recientes primero).
    """
    appointments = await app.state.appointment_manager.get_appointments_by_session(session_id)
    formatted_appointments = [
        app.state.appointment_manager.format_appointment_for_response(apt) 
        for apt in appointments
    ]
    
    return {
        "session_id": session_id,
        "appointments": formatted_appointments,
        "total_appointments": len(formatted_appointments)
    }


@app.get("/appointment/{appointment_id}", tags=["Appointments"])
async def get_appointment_by_id(appointment_id: str):
    """
    📅 Obtiene una cita específica por su ID.
    
    Devuelve todos los detalles de una cita específica incluyendo
    el análisis de conversación y metadatos extraídos.
    """
    appointment = await app.state.appointment_manager.get_appointment_by_id(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return app.state.appointment_manager.format_appointment_for_response(appointment)


@app.get("/appointments/recent", tags=["Appointments"])
async def get_recent_appointments(limit: int = 10):
    """
    📅 Obtiene las citas más recientes.
    
    Devuelve las citas más recientes del sistema, útiles para
    monitoreo y gestión de citas.
    """
    appointments = await app.state.appointment_manager.get_recent_appointments(limit)
    formatted_appointments = [
        app.state.appointment_manager.format_appointment_for_response(apt) 
        for apt in appointments
    ]
    
    return {
        "appointments": formatted_appointments,
        "total_appointments": len(formatted_appointments),
        "limit": limit
    }


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
