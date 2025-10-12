import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import (
    ChatRequest, MapSearchRequest, ChatResponse,
    ConversationHistoryResponse, HealthResponse,
    AppointmentRequest, AppointmentResponse,
    PropertySearchRequest, PropertySearchResponse
)
from app.services.ai_parse import get_llm_result, validate_and_correct_location
from app.services.appointment_analyzer import AppointmentAnalyzer
from app.services.appointment_manager import AppointmentManager
from app.services.aura_property_manager import AuraPropertyManager
from app.services.concurrency_manager import RequestLimiter, AsyncTaskManager
from app.services.email_service import EmailService
from app.services.idealista_hook import get_idealista_properties
from app.services.intent_classifier import IntentClassifier, SeniorRealEstateAgent
from app.services.memory_manager import ConversationMemory
from app.services.property_manager import PropertyManager
from app.services.property_summarizer import PropertySummarizer
from app.services.quality_filter import PropertyQualityFilter
from utils import get_area_by_giving_location, to_idealista_multipolygon, create_meter_radius_circle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CITY = 'Madrid, España'
def generate_search_suggestions(prompt_result: dict) -> str:
    """Genera sugerencias cuando no se encuentran propiedades"""
    suggestions = []
    if prompt_result.get('maxPrice'):
        suggestions.append(f"• Aumentar el presupuesto máximo (actual: {prompt_result['maxPrice']:,}€)")

    if prompt_result.get('minRooms'):
        suggestions.append(f"• Reducir el número mínimo de habitaciones (actual: {prompt_result['minRooms']})")

    if prompt_result.get('minSize'):
        suggestions.append(f"• Reducir los metros cuadrados mínimos (actual: {prompt_result['minSize']}m²)")

    if prompt_result.get('locationName'):
        suggestions.append(f"• Ampliar la zona de búsqueda alrededor de {prompt_result['locationName']}")

    suggestions.extend([
        "• Considerar propiedades en zonas cercanas",
        "• Revisar si hay propiedades similares con características ligeramente diferentes",
        "• Contactar con un agente inmobiliario para búsquedas personalizadas"
    ])

    return "Te sugiero:\n" + "\n".join(suggestions[:4])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor del ciclo de vida de la aplicación con lazy loading"""
    logger.info("Starting Aura Backend MVP...")

    app.state.request_limiter = RequestLimiter(max_concurrent=10, rate_limit_per_minute=100)
    app.state.task_manager = AsyncTaskManager()
    app.state._services_initialized = False
    app.state._services = {}

    logger.info("Core services initialized successfully")

    yield

    logger.info("Shutting down Aura Backend MVP...")

    if hasattr(app.state, 'task_manager'):
        for task_id in list(app.state.task_manager.tasks.keys()):
            await app.state.task_manager.cancel_task(task_id)

    if hasattr(app.state, 'request_limiter'):
        await app.state.request_limiter.cleanup_old_requests()

    logger.info("Cleanup completed")


def get_service(app, service_name: str):
    """Lazy loading de servicios"""
    if not hasattr(app.state, '_services_initialized') or not app.state._services_initialized:
        app.state._services_initialized = True
        app.state._services = {
            'memory_manager': ConversationMemory(),
            'property_manager': PropertyManager(),
            'quality_filter': PropertyQualityFilter(),
            'summarizer': PropertySummarizer(),
            'intent_classifier': IntentClassifier(),
            'senior_agent': SeniorRealEstateAgent(),
            'appointment_manager': AppointmentManager(),
            'appointment_analyzer': AppointmentAnalyzer(),
            'email_service': EmailService(),
            'aura_property_manager': AuraPropertyManager()
        }
        logger.info("All services initialized with lazy loading")

    return app.state._services.get(service_name)


app = FastAPI(
    title="Aura Backend MVP",
    description="""
    Backend API para asistencia inmobiliaria inteligente
    
    Endpoints disponibles:
    - POST /chat: Chat inteligente con clasificación de intenciones
    - POST /maps: Búsqueda por coordenadas geográficas
    - POST /appointment: Crear cita inmobiliaria con análisis IA
    - POST /properties/search: Buscar propiedades por IDs específicos
    - GET /conversation/{session_id}: Obtener historial de conversación
    - GET /appointments/{session_id}: Obtener citas de una sesión
    - GET /appointment/{appointment_id}: Obtener cita específica
    - GET /health: Estado del servicio y conexiones
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root():
    """Endpoint raíz con información del servicio"""
    return {
        "message": "Bienvenido al Backend MVP de Aura",
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
            "Notificaciones por email",
            "Búsqueda de propiedades por IDs"
        ]
    }


@app.post("/chat", response_model=ChatResponse, tags=["Search"])
async def chat_search(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Chat inteligente con clasificación de intenciones y memoria.

    Procesa consultas en lenguaje natural:
    1. Clasifica la intención del usuario usando IA
    2. Si busca propiedades: Procesa la búsqueda con LLM y devuelve resultados
    3. Si es consulta general: Responde como un senior de inmobiliaria experto
    4. Mantiene memoria de la conversación para contexto continuo y guarda las propiedades consultadas
    """
    session_id = request.session_id

    # Verificar límite de concurrencia
    try:
        await app.state.request_limiter.acquire(session_id)
    except HTTPException as e:
        raise e

    try:
        memory_manager = get_service(app, 'memory_manager')
        history_task = memory_manager.get_conversation_history(session_id)

        background_tasks.add_task(
            memory_manager.save_message,
            session_id, "user", request.prompt, None, request.ip_address
        )

        history = await history_task
        conversation_context = memory_manager.format_history_for_llm(history)

        intent_classifier = get_service(app, 'intent_classifier')
        intent_classification = await intent_classifier.classify_intent(
            request.prompt, conversation_context
        )

        logger.info(f"Intent classification: {intent_classification}")

        # SI NO ES BÚSQUEDA DE PROPIEDADES, RESPONDER COMO SENIOR DE INMOBILIARIA
        if intent_classification["intent"] == "general_inquiry":
            senior_agent = get_service(app, 'senior_agent')
            senior_response = await senior_agent.generate_response(
                request.prompt, conversation_context
            )

            # Guardar respuesta del senior en background
            background_tasks.add_task(
                memory_manager.save_message,
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
        # SI ES BÚSQUEDA DE PROPIEDADES, CONTINUAR CON EL FLUJO DE SCRAPPEAR INMUEBLES
        enhanced_prompt = f"{conversation_context}\n\nNueva consulta: {request.prompt}"

        if not enhanced_prompt.strip():
            raise ValueError("Prompt vacío o inválido")

        loop = asyncio.get_event_loop()
        llm_task = loop.run_in_executor(None, get_llm_result, enhanced_prompt)
        location_from_prompt = request.prompt.lower()
        location_validation_task = loop.run_in_executor(
            None, validate_and_correct_location, location_from_prompt, DEFAULT_CITY
        )

        # Esperar ambos resultados en paralelo
        prompt_result, location_validation = await asyncio.gather(
            llm_task, location_validation_task
        )

        if "locationName" not in prompt_result:
            raise ValueError("No se especificó ubicación en la consulta")

        best_location = location_validation["corrected_location"] if location_validation["confidence"] > 0.7 else \
        prompt_result["locationName"]

        if location_validation["confidence"] > 0.7:
            logger.info(f"Using corrected location: {location_validation['corrected_location']}")
        else:
            logger.warning(f"Low confidence location: {location_validation['reason']}")

        coordinates_task = loop.run_in_executor(
            None, get_area_by_giving_location, best_location
        )

        prompt_result_copy = prompt_result.copy()
        prompt_result_copy['limit'] = min(request.limit * 2, 50)

        coordinates = await coordinates_task
        geojson_str = to_idealista_multipolygon(coordinates)
        prompt_result_copy['shape'] = geojson_str

        df_raw, records_raw = await get_idealista_properties(prompt_result_copy)

        if df_raw.empty:
            # Generar mensaje de sugerencias para el usuario
            suggestions = generate_search_suggestions(prompt_result)
            no_properties_message = f"No se encontraron propiedades con los criterios especificados. {suggestions}"

            background_tasks.add_task(
                memory_manager.save_message,
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

        quality_filter = get_service(app, 'quality_filter')
        df = quality_filter.filter_and_rank_properties(
            df_raw,
            top_n=request.limit,
            paraphrase_descriptions=False,
            max_concurrent=1
        )

        records = df.head(request.limit).to_dict(orient='records')

        summarizer = get_service(app, 'summarizer')

        if records:
            summary_context = f"Consulta: {request.prompt}"
            summary = await summarizer.generate_summary(
                records,
                first_top_properties=request.limit,
                conversation_context=summary_context,
                total_properties=records_raw.get('total', 0)
            )
        else:
            summary = "No he encontrado propiedades que coincidan exactamente con tu búsqueda. Te sugiero ampliar los criterios o probar con una zona cercana."

        prompt_result_clean = prompt_result.copy()
        prompt_result_clean.pop('shape', None)
        property_list = df['propertyCode'].tolist() if not df.empty else []

        property_manager = get_service(app, 'property_manager')
        properties_data = df_raw.head(request.limit).to_dict('records') if not df_raw.empty else []

        message_metadata = {
            "properties_found": len(records),
            "search_params": prompt_result_clean,
            "property_list": property_list,
            "llm_summary": summary
        }

        background_tasks.add_task(
            property_manager.save_properties,
            properties_data
        )

        background_tasks.add_task(
            memory_manager.save_message,
            session_id, "assistant", summary,
            message_metadata, request.ip_address
        )

        # Preparar respuesta final
        response_data = {
            'llm_summary': summary,
            'properties': records,
            'total_found': len(df),
            'session_id': session_id,
            'search_params': prompt_result_clean
        }

        return ChatResponse(**response_data)

    except ValueError as e:
        logger.warning(f"Validation error in chat_search: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Error de validación: {str(e)}")
    except ConnectionError as e:
        logger.error(f"Connection error in chat_search: {str(e)}")
        raise HTTPException(status_code=503, detail="Servicio temporalmente no disponible")
    except TimeoutError as e:
        logger.error(f"Timeout error in chat_search: {str(e)}")
        raise HTTPException(status_code=504, detail="Timeout en la operación")
    except Exception as e:
        logger.error(f"Unexpected error in chat_search: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

    finally:
        app.state.request_limiter.release(session_id)


@app.post("/maps", response_model=ChatResponse, tags=["Search"])
async def maps_search(request: MapSearchRequest, background_tasks: BackgroundTasks):
    """
    Búsqueda de propiedades por coordenadas geográficas.

    Busca propiedades en un radio específico alrededor de las coordenadas proporcionadas,
    aplicando filtros de calidad y generando resúmenes automáticos.
    """
    session_id = request.session_id

    try:
        await app.state.request_limiter.acquire(session_id)
    except HTTPException as e:
        raise e

    try:
        # Crear círculo de búsqueda
        circle = create_meter_radius_circle(request.lat, request.lng, request.metro)
        multipolygon_str = to_idealista_multipolygon(circle)
        prompt_result_final = {'shape': multipolygon_str}
        df_raw, records_raw = await get_idealista_properties(prompt_result_final)

        if df_raw.empty:
            # Generar mensaje de sugerencias para el usuario
            suggestions = f"• Ampliar el radio de búsqueda (actual: {request.metro}m)\n• Considerar coordenadas cercanas\n• Revisar si hay propiedades en zonas adyacentes"
            no_properties_message = f"No se encontraron propiedades en el radio de {request.metro}m desde las coordenadas especificadas. {suggestions}"

            memory_manager = get_service(app, 'memory_manager')
            background_tasks.add_task(
                memory_manager.save_message,
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

        quality_filter = get_service(app, 'quality_filter')
        df = quality_filter.filter_and_rank_properties(
            df_raw,
            top_n=request.limit,
            paraphrase_descriptions=False,
            max_concurrent=5
        )

        records = df.head(request.limit).to_dict(orient='records')
        search_description = f"Búsqueda en radio de {request.metro}m desde coordenadas ({request.lat}, {request.lng})"
        summarizer = get_service(app, 'summarizer')
        summary = await summarizer.generate_summary(
            records,
            first_top_properties=request.limit,
            conversation_context=search_description,
            total_properties=len(df)
        )

        property_list = df['propertyCode'].tolist() if not df.empty else []
        memory_manager = get_service(app, 'memory_manager')

        background_tasks.add_task(
            memory_manager.save_message,
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

    except ValueError as e:
        logger.warning(f"Validation error in maps_search: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Error de validación: {str(e)}")
    except ConnectionError as e:
        logger.error(f"Connection error in maps_search: {str(e)}")
        raise HTTPException(status_code=503, detail="Servicio temporalmente no disponible")
    except TimeoutError as e:
        logger.error(f"Timeout error in maps_search: {str(e)}")
        raise HTTPException(status_code=504, detail="Timeout en la operación")
    except Exception as e:
        logger.error(f"Unexpected error in maps_search: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

    finally:
        app.state.request_limiter.release(session_id)


@app.get("/conversation/{session_id}", response_model=ConversationHistoryResponse, tags=["Memory"])
async def get_conversation_history(session_id: str):
    """
    Obtiene el historial de conversación de una sesión específica.

    Permite recuperar el contexto completo de una conversación para mantener
    la continuidad en las búsquedas de propiedades.
    """
    memory_manager = get_service(app, 'memory_manager')
    history = await memory_manager.get_conversation_history(session_id)
    return ConversationHistoryResponse(
        session_id=session_id,
        history=history,
        message_count=len(history)
    )


@app.get("/properties/{session_id}", tags=["Properties"])
async def get_properties_by_session(session_id: str, limit: int = 50):
    """
    Obtiene las propiedades relacionadas con una sesión específica.

    Devuelve las propiedades que han sido mostradas en las conversaciones
    de la sesión especificada, limitadas a los últimos registros.
    """
    property_manager = get_service(app, 'property_manager')
    properties = await property_manager.get_properties_by_session(session_id, limit=limit)
    return {
        "session_id": session_id,
        "properties": properties,
        "total_properties": len(properties),
        "limit": limit
    }


@app.get("/property/exclusive", tags=["Properties"])
async def get_exclusive_properties():
    """
    Obtiene todas las propiedades exclusivas de Aura en orden aleatorio.

    Este endpoint devuelve todas las propiedades de la tabla `aura_properties`
    en un orden aleatorio diferente cada vez que se llama.
    """
    try:
        logger.info("Fetching exclusive Aura properties...")
        aura_property_manager = get_service(app, 'aura_property_manager')
        properties = await aura_property_manager.get_exclusive_properties_random()
        logger.info(f"Retrieved {len(properties)} exclusive properties")

        return {
            "properties": properties,
            "total_properties": len(properties),
            "message": "Propiedades exclusivas de Aura obtenidas en orden aleatorio",
            "timestamp": datetime.now().isoformat()
        }

    except ConnectionError as e:
        logger.error(f"Connection error getting exclusive properties: {str(e)}")
        raise HTTPException(status_code=503, detail="Servicio temporalmente no disponible")
    except Exception as e:
        logger.error(f"Error getting exclusive properties: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Endpoint de health check con estado de conexiones"""
    from app.services.supabase_helper import get_supabase_client
    supabase_connected = get_supabase_client() is not None

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        supabase_connected=supabase_connected
    )


@app.post("/appointment", response_model=AppointmentResponse, tags=["Appointments"])
async def create_appointment(request: AppointmentRequest, http_request: Request, background_tasks: BackgroundTasks):
    """
    Crea una nueva cita inmobiliaria.

    Este endpoint:
    1. Analiza el historial de conversación del usuario usando IA
    2. Extrae información relevante: presupuesto, ubicación, financiación, preferencias
    3. Detecta la ubicación del usuario basada en su IP
    4. Guarda la cita en la base de datos
    5. Envía notificación por email con toda la información extraída
    """

    try:
        if request.property_id and not request.property_url:
            property_url = f"https://www.idealista.com/inmueble/{request.property_id}/"
        else:
            property_url = request.property_url
        
        client_ip = http_request.client.host if http_request.client else "unknown"
        if client_ip == "testclient":
            client_ip = "127.0.0.1"
        try:
            await app.state.request_limiter.acquire(request.session_id)
        except HTTPException as e:
            raise e

        try:
            logger.info(f"Obteniendo historial para sesión: {request.session_id}")
            memory_manager = get_service(app, 'memory_manager')
            memory_manager.max_history = 20
            conversation_history = await memory_manager.get_conversation_history(request.session_id)

            logger.info("Analizando conversación con IA...")
            appointment_analyzer = get_service(app, 'appointment_analyzer')
            analysis_result = await appointment_analyzer.analyze_conversation_history(
                conversation_history, client_ip
            )

            conversation_summary = appointment_analyzer.create_conversation_summary(
                conversation_history, analysis_result
            )
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
                "need_finance": request.need_finance,
                "time_searching": request.time_searching,
                "utms": request.utms or {},
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

            logger.info("Guardando appointment en base de datos...")
            appointment_manager = get_service(app, 'appointment_manager')
            created_appointment = await appointment_manager.create_appointment(appointment_data)

            response_data = appointment_manager.format_appointment_for_response(created_appointment)

            logger.info("Programando envío de email...")
            email_service = get_service(app, 'email_service')
            background_tasks.add_task(
                email_service.send_appointment_notification,
                response_data
            )

            logger.info(f"Appointment creado exitosamente: {created_appointment['id']}")

            return AppointmentResponse(**response_data)

        except ValueError as e:
            logger.warning(f"Validation error creating appointment: {str(e)}")
            raise HTTPException(status_code=422, detail=f"Error de validación: {str(e)}")
        except ConnectionError as e:
            logger.error(f"Connection error creating appointment: {str(e)}")
            raise HTTPException(status_code=503, detail="Servicio temporalmente no disponible")
        except Exception as e:
            logger.error(f"Error creando appointment: {str(e)}")
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
    Obtiene todas las citas de una sesión específica.

    Devuelve todas las citas programadas para la sesión especificada,
    ordenadas por fecha de creación (más recientes primero).
    """
    appointment_manager = get_service(app, 'appointment_manager')
    appointments = await appointment_manager.get_appointments_by_session(session_id)
    formatted_appointments = [
        appointment_manager.format_appointment_for_response(apt)
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
    Obtiene una cita específica por su ID.

    Devuelve todos los detalles de una cita específica incluyendo
    el análisis de conversación y metadatos extraídos.
    """
    appointment_manager = get_service(app, 'appointment_manager')
    appointment = await appointment_manager.get_appointment_by_id(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return appointment_manager.format_appointment_for_response(appointment)


@app.post("/properties/search", response_model=PropertySearchResponse, tags=["Properties"])
async def search_properties_by_ids(request: PropertySearchRequest):
    """
    Busca propiedades por sus IDs (property codes).

    Este endpoint permite buscar propiedades específicas en la base de datos
    usando sus códigos de propiedad. Acepta tanto un string individual como
    una lista de IDs.
    """
    try:
        property_ids = request.property_ids
        logger.info(f"Searching for properties with IDs: {property_ids}")

        property_manager = get_service(app, 'property_manager')
        search_result = await property_manager.get_properties_by_codes(property_ids)

        response = PropertySearchResponse(
            found_properties=search_result['found_properties'],
            total_found=len(search_result['found_properties']),
            requested_ids=property_ids,
            not_found_ids=search_result['not_found_codes']
        )

        logger.info(f"Property search completed: {response.total_found} found, {len(response.not_found_ids)} not found")

        return response

    except ValueError as e:
        logger.warning(f"Validation error in search_properties_by_ids: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Error de validación: {str(e)}")
    except ConnectionError as e:
        logger.error(f"Connection error in search_properties_by_ids: {str(e)}")
        raise HTTPException(status_code=503, detail="Servicio temporalmente no disponible")
    except Exception as e:
        logger.error(f"Error in search_properties_by_ids: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/stats", tags=["General"])
async def get_service_stats():
    """Obtiene estadísticas del servicio"""
    return {
        "active_requests": app.state.request_limiter.get_active_requests_count(),
        "active_tasks": len(app.state.task_manager.tasks),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/new_prompt", tags=["Legacy"])
async def new_prompt_legacy(request: dict):
    """
    Endpoint legacy mantenido para compatibilidad.
    
    Se recomienda usar `/chat` para nuevas implementaciones.
    """
    logger.warning("Using legacy endpoint /new_prompt. Consider migrating to /chat")

    chat_request = ChatRequest(
        prompt=request.get("prompt", ""),
        limit=int(request.get("limit", 200)),
        session_id=request.get("session_id"),
        ip_address=request.get("ip_address")
    )

    return await chat_search(chat_request, BackgroundTasks())


@app.post("/new_maps", tags=["Legacy"])
async def new_maps_legacy(request: dict):
    """
    Endpoint legacy mantenido para compatibilidad.
    
    Se recomienda usar `/maps` para nuevas implementaciones.
    """
    logger.warning("Using legacy endpoint /new_maps. Consider migrating to /maps")

    maps_request = MapSearchRequest(
        lng=float(request.get("lng", 0)),
        lat=float(request.get("lat", 0)),
        limit=int(request.get("limit", 200)),
        metro=int(request.get("metro", 1000)),
        session_id=request.get("session_id"),
        ip_address=request.get("ip_address")
    )

    return await maps_search(maps_request, BackgroundTasks())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
