"""
Servicio para analizar el historial de conversaciones y extraer información relevante para citas
"""

import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import AsyncOpenAI
from app.config import Config
from utils import LLMModel, LLMVersion

logger = logging.getLogger(__name__)

class AppointmentAnalyzer:
    """Analizador de conversaciones para extraer información relevante para citas"""
    
    def __init__(self):
        self.async_client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
    
    async def analyze_conversation_history(self, conversation_history: List[Dict[str, Any]], user_ip: str = None) -> Dict[str, Any]:
        """
        Analiza el historial de conversación para extraer información relevante usando get_llm_result
        
        Args:
            conversation_history: Lista de mensajes de la conversación
            user_ip: IP del usuario para detectar ubicación
            
        Returns:
            Dict con información extraída: budget_min, budget_max, location, financing, metadata
        """
        try:
            # Formatear historial y crear prompt
            formatted_history = self._format_history_for_analysis(conversation_history)
            analysis_prompt = self._create_analysis_prompt(formatted_history, user_ip)
            
            # Llamar al LLM de forma asíncrona
            analysis_result = await self._get_async_llm_result(
                prompt=analysis_prompt,
                system_instruction=self._get_analysis_system_instruction()
            )
            
            # Procesar y validar resultado
            processed_result = self._process_analysis_result(analysis_result)
            
            logger.info(f"Análisis de conversación completado: {processed_result}")
            return processed_result
            
        except Exception as e:
            logger.error(f"Error analizando historial de conversación: {str(e)}")
            return self._get_default_analysis()
    
    def _format_history_for_analysis(self, conversation_history: List[Dict[str, Any]]) -> str:
        """Formatea el historial para el análisis del LLM"""
        formatted_messages = []
        
        for message in conversation_history:
            role = message.get('role', 'unknown')
            content = message.get('content', '')
            timestamp = message.get('created_at', '')
            
            if role in ['user', 'assistant']:
                # Hacer más claro quién es quién
                if role == 'user':
                    formatted_messages.append(f"CLIENTE: {content}")
                elif role == 'assistant':
                    formatted_messages.append(f"ASISTENTE: {content}")
        
        return "\n".join(formatted_messages)
    
    async def _get_async_llm_result(self, prompt: str, system_instruction: str) -> Dict[str, Any]:
        """Obtiene respuesta del LLM de forma asíncrona"""
        try:
            # FIXED: Add "json" to the user message to comply with OpenAI requirements
            full_prompt = f"""
            Usuario: {prompt}

            Por favor, responde en formato JSON válido.
            """

            response = await self.async_client.chat.completions.create(
                model=LLMVersion.OPENAI_4_1_NANO.value,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = response.choices[0].message.content
            logging.info(f"OpenAI Response: {result}")
            return json.loads(result)
            
        except Exception as e:
            logging.error(f"Error en llamada asíncrona a OpenAI: {str(e)}")
            raise
    
    def _get_analysis_system_instruction(self) -> str:
        """Retorna las instrucciones del sistema para el análisis de conversaciones"""
        return """
Eres un experto analista de conversaciones inmobiliarias. Tu tarea es analizar el historial de conversación de un cliente y extraer TODA la información relevante para que el equipo de ventas tenga un contexto completo.

IMPORTANTE: 
- USER = Cliente (lo que dice el cliente)
- ASSISTANT = Asistente inmobiliario (respuestas del sistema)
- SOLO analiza lo que dice el CLIENTE (USER), ignora las respuestas del asistente
- NO uses presupuestos, precios o información que mencione el ASSISTANT
- EXTRAE TODOS los detalles específicos mencionados por el cliente
- CAPTURA frases exactas o palabras clave importantes del cliente

INSTRUCCIONES DETALLADAS:
Analiza cuidadosamente SOLO los mensajes del CLIENTE (USER) y extrae la siguiente información:

1. PRESUPUESTO (solo del cliente):
   - Presupuesto mínimo mencionado por el CLIENTE (budget_min)
   - Presupuesto máximo mencionado por el CLIENTE (budget_max)
   - Si el cliente menciona rangos como "entre X e Y", extrae ambos valores
   - Si el cliente solo menciona "máximo X" o "hasta X", usa ese como budget_max
   - Si el cliente solo menciona "mínimo X" o "desde X", usa ese como budget_min
   - IGNORA cualquier precio o presupuesto mencionado por el ASSISTANT

2. UBICACIÓN (solo del cliente):
   - Localización específica mencionada por el CLIENTE (ciudad, barrio, zona, dirección)
   - Preferencias de ubicación expresadas por el CLIENTE
   - Cualquier descripción de la zona (segura, tranquila, céntrica, etc.)

3. CARACTERÍSTICAS FÍSICAS (solo del cliente):
   - Tipo de propiedad mencionado por el CLIENTE (piso, casa, apartamento, etc.)
   - Número de habitaciones solicitado por el CLIENTE
   - Número de baños mencionado por el CLIENTE
   - Metros cuadrados mencionados por el CLIENTE (min_size, max_size)
   - Planta o piso mencionado por el CLIENTE

4. CARACTERÍSTICAS ESPECIALES (solo del cliente):
   - Garaje, parking, plaza de garaje
   - Terraza, balcón, azotea
   - Jardín, patio, exterior
   - Ascensor, elevador
   - Aire acondicionado, climatización
   - Piscina, gimnasio, spa
   - Lujo, de lujo, premium
   - Reformado, nuevo, a estrenar
   - Amueblado, sin amueblar

5. PREFERENCIAS DE CALIDAD/ESTADO (solo del cliente):
   - Palabras como: seguro, segura, tranquilo, tranquila
   - Prometido, prometedor, con futuro
   - Nuevo, reformado, moderno, clásico
   - Bien comunicado, cerca del metro, transporte
   - Zona residencial, comercial, mixta

6. FINANCIACIÓN (solo del cliente):
   - Si el CLIENTE menciona necesidad de financiación, hipoteca, préstamo
   - Si el CLIENTE pregunta sobre opciones de pago
   - Si el CLIENTE menciona ser primera vivienda (puede necesitar financiación)
   - Entrada, enganche, capital inicial mencionado

7. CONTEXTO PERSONAL (solo del cliente):
   - Situación familiar mencionada por el CLIENTE (pareja, hijos, etc.)
   - Motivo de compra expresado por el CLIENTE (primera vivienda, inversión, etc.)
   - Urgencia o timeline mencionado por el CLIENTE
   - Trabajo, oficina, desplazamiento mencionado

8. INFORMACIÓN ADICIONAL (solo del cliente):
   - Cualquier detalle específico, preferencia o requisito mencionado
   - Frases exactas importantes del cliente
   - Aspectos que el cliente enfatiza o repite

FORMATO DE RESPUESTA (JSON):
{
    "budget_min": null o número entero,
    "budget_max": null o número entero,
    "location": "ubicación mencionada o inferida",
    "location_description": "descripción de la zona (segura, tranquila, etc.)",
    "financing": true/false,
    "property_type": "tipo de propiedad mencionado",
    "bedrooms": null o número,
    "bathrooms": null o número,
    "min_size": null o número (metros cuadrados),
    "max_size": null o número (metros cuadrados),
    "floor": "planta o piso mencionado",
    "special_features": ["lista", "de", "características"],
    "quality_preferences": ["seguro", "prometido", "nuevo", "etc"],
    "personal_context": "contexto personal relevante",
    "urgency": "alta/media/baja",
    "additional_requirements": "cualquier requisito adicional específico",
    "client_quotes": ["frases", "exactas", "importantes", "del", "cliente"],
    "preferences_summary": "resumen detallado de todas las preferencias"
}

IMPORTANTE:
- Si no se menciona algo específico, usa null para números y "" para strings
- CAPTURA TODOS los detalles específicos mencionados
- Incluye frases exactas importantes del cliente en client_quotes
- Para quality_preferences, incluye palabras como "seguro", "prometido", "tranquilo", etc.
- Sé exhaustivo en la extracción de información
- El preferences_summary debe ser muy detallado para el equipo de ventas
"""
    
    def _create_analysis_prompt(self, formatted_history: str, user_ip: str = None) -> str:
        """Crea el prompt para el análisis del LLM"""
        
        ip_context = ""
        if user_ip:
            ip_context = f"\n\nIP del usuario: {user_ip} (puede ayudar a determinar ubicación geográfica)"
        
        return f"""
HISTORIAL DE CONVERSACIÓN:
{formatted_history}
{ip_context}

Analiza este historial de conversación y extrae la información relevante según las instrucciones del sistema.
"""
    
    def _process_analysis_result(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa y valida el resultado del LLM"""
        try:
            # get_llm_result ya retorna un diccionario parseado
            analysis_data = llm_response
            
            # Validar y limpiar datos
            processed_data = {
                "budget_min": self._safe_int(analysis_data.get("budget_min")),
                "budget_max": self._safe_int(analysis_data.get("budget_max")),
                "location": self._safe_str(analysis_data.get("location")),
                "location_description": self._safe_str(analysis_data.get("location_description")),
                "financing": bool(analysis_data.get("financing", False)),
                "property_type": self._safe_str(analysis_data.get("property_type")),
                "bedrooms": self._safe_int(analysis_data.get("bedrooms")),
                "bathrooms": self._safe_int(analysis_data.get("bathrooms")),
                "min_size": self._safe_int(analysis_data.get("min_size")),
                "max_size": self._safe_int(analysis_data.get("max_size")),
                "floor": self._safe_str(analysis_data.get("floor")),
                "special_features": self._safe_list(analysis_data.get("special_features")),
                "quality_preferences": self._safe_list(analysis_data.get("quality_preferences")),
                "personal_context": self._safe_str(analysis_data.get("personal_context")),
                "urgency": self._safe_str(analysis_data.get("urgency", "media")) or "media",
                "additional_requirements": self._safe_str(analysis_data.get("additional_requirements")),
                "client_quotes": self._safe_list(analysis_data.get("client_quotes")),
                "preferences_summary": self._safe_str(analysis_data.get("preferences_summary"))
            }
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error procesando resultado del análisis: {str(e)}")
            logger.error(f"Respuesta del LLM: {llm_response}")
            return self._get_default_analysis()
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Convierte valor a int de forma segura"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_str(self, value: Any) -> Optional[str]:
        """Convierte valor a string de forma segura"""
        if value is None:
            return None
        try:
            # Si es una lista, convertir a string separado por comas
            if isinstance(value, list):
                return ', '.join(str(item) for item in value) or None
            return str(value).strip() or None
        except (ValueError, TypeError):
            return None
    
    def _safe_list(self, value: Any) -> List[str]:
        """Convierte valor a lista de forma segura"""
        if value is None:
            return []
        try:
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str):
                return [value.strip()] if value.strip() else []
            else:
                return [str(value).strip()] if str(value).strip() else []
        except (ValueError, TypeError):
            return []
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Retorna análisis por defecto en caso de error"""
        return {
            "budget_min": None,
            "budget_max": None,
            "location": None,
            "location_description": None,
            "financing": False,
            "property_type": None,
            "bedrooms": None,
            "bathrooms": None,
            "min_size": None,
            "max_size": None,
            "floor": None,
            "special_features": [],
            "quality_preferences": [],
            "personal_context": None,
            "urgency": "media",
            "additional_requirements": None,
            "client_quotes": [],
            "preferences_summary": None
        }
    
    async def get_user_location_from_ip(self, ip_address: str) -> Optional[str]:
        """
        Obtiene la ubicación del usuario basada en su IP
        
        Args:
            ip_address: Dirección IP del usuario
            
        Returns:
            Ubicación detectada o None si no se puede determinar
        """
        try:
            # Para IPs locales o de desarrollo, retornar None
            if ip_address in ['127.0.0.1', 'localhost', '::1'] or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
                return None
            
            # Aquí podrías integrar un servicio de geolocalización por IP
            # Por ahora, retornamos None para evitar llamadas externas innecesarias
            logger.info(f"IP detectada: {ip_address} (geolocalización no implementada)")
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo ubicación por IP: {str(e)}")
            return None
    
    def create_conversation_summary(self, conversation_history: List[Dict[str, Any]], analysis_data: Dict[str, Any]) -> str:
        """
        Crea un resumen detallado de la conversación para el email del equipo de ventas
        
        Args:
            conversation_history: Historial de conversación
            analysis_data: Datos extraídos del análisis
            
        Returns:
            Resumen detallado formateado de la conversación
        """
        try:
            # Contar mensajes
            user_messages = [msg for msg in conversation_history if msg.get('role') == 'user']
            assistant_messages = [msg for msg in conversation_history if msg.get('role') == 'assistant']
            
            # Crear resumen detallado
            summary_parts = []
            
            # Información básica
            summary_parts.append(f"📞 Cliente ha tenido {len(user_messages)} consultas en la conversación.")
            
            # Presupuesto
            if analysis_data.get('budget_min') or analysis_data.get('budget_max'):
                budget_info = []
                if analysis_data.get('budget_min'):
                    budget_info.append(f"mínimo {analysis_data['budget_min']:,}€")
                if analysis_data.get('budget_max'):
                    budget_info.append(f"máximo {analysis_data['budget_max']:,}€")
                summary_parts.append(f"💰 Presupuesto: {' - '.join(budget_info)}")
            
            # Ubicación
            if analysis_data.get('location'):
                location_info = f"📍 Ubicación: {analysis_data['location']}"
                if analysis_data.get('location_description'):
                    location_info += f" ({analysis_data['location_description']})"
                summary_parts.append(location_info)
            
            # Tipo de propiedad y características físicas
            property_info = []
            if analysis_data.get('property_type'):
                property_info.append(analysis_data['property_type'])
            if analysis_data.get('bedrooms'):
                property_info.append(f"{analysis_data['bedrooms']} habitaciones")
            if analysis_data.get('bathrooms'):
                property_info.append(f"{analysis_data['bathrooms']} baños")
            if analysis_data.get('min_size') or analysis_data.get('max_size'):
                size_info = []
                if analysis_data.get('min_size'):
                    size_info.append(f"mín. {analysis_data['min_size']}m²")
                if analysis_data.get('max_size'):
                    size_info.append(f"máx. {analysis_data['max_size']}m²")
                property_info.append(f"Superficie: {' - '.join(size_info)}")
            if analysis_data.get('floor'):
                property_info.append(f"Planta: {analysis_data['floor']}")
            
            if property_info:
                summary_parts.append(f"🏠 Propiedad: {', '.join(property_info)}")
            
            # Características especiales
            if analysis_data.get('special_features'):
                features = ', '.join(analysis_data['special_features'])
                summary_parts.append(f"✨ Características: {features}")
            
            # Preferencias de calidad
            if analysis_data.get('quality_preferences'):
                quality = ', '.join(analysis_data['quality_preferences'])
                summary_parts.append(f"⭐ Preferencias de calidad: {quality}")
            
            # Financiación
            if analysis_data.get('financing'):
                summary_parts.append("🏦 Necesita financiación/hipoteca")
            
            # Contexto personal
            if analysis_data.get('personal_context'):
                summary_parts.append(f"👤 Contexto personal: {analysis_data['personal_context']}")
            
            # Requisitos adicionales
            if analysis_data.get('additional_requirements'):
                summary_parts.append(f"📋 Requisitos adicionales: {analysis_data['additional_requirements']}")
            
            # Urgencia
            if analysis_data.get('urgency') and analysis_data['urgency'] != 'media':
                urgency_emoji = {"alta": "🚨", "baja": "⏰"}.get(analysis_data['urgency'], "⏱️")
                summary_parts.append(f"{urgency_emoji} Urgencia: {analysis_data['urgency']}")
            
            # Frases importantes del cliente
            if analysis_data.get('client_quotes'):
                quotes = ' | '.join([f'"{quote}"' for quote in analysis_data['client_quotes'][:3]])  # Máximo 3 frases
                summary_parts.append(f"💬 Frases del cliente: {quotes}")
            
            # Resumen detallado si está disponible
            if analysis_data.get('preferences_summary'):
                summary_parts.append(f"📝 Resumen detallado: {analysis_data['preferences_summary']}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error creando resumen de conversación: {str(e)}")
            return f"Cliente ha tenido {len(conversation_history)} mensajes en la conversación."
    
    def combine_with_metadata(self, analysis_data: Dict[str, Any], conversation_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Combina la información extraída del análisis con los metadatos de la conversación
        
        Args:
            analysis_data: Datos extraídos del análisis de conversación
            conversation_metadata: Metadatos adicionales de la conversación
            
        Returns:
            Diccionario combinado con toda la información relevante
        """
        try:
            combined_data = analysis_data.copy()
            
            if conversation_metadata:
                # Agregar metadatos relevantes
                if 'search_params' in conversation_metadata:
                    search_params = conversation_metadata['search_params']
                    
                    # Si hay parámetros de búsqueda, agregarlos como información adicional
                    if 'intent' in search_params:
                        combined_data['search_intent'] = search_params['intent']
                    
                    if 'classification' in search_params:
                        combined_data['intent_classification'] = search_params['classification']
                
                # Agregar otros metadatos relevantes
                for key, value in conversation_metadata.items():
                    if key not in ['search_params'] and value is not None:
                        combined_data[f'metadata_{key}'] = value
            
            return combined_data
            
        except Exception as e:
            logger.error(f"Error combinando con metadatos: {str(e)}")
            return analysis_data
