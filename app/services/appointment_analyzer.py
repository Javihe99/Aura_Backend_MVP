"""
Servicio para analizar el historial de conversaciones y extraer información relevante para citas
"""

import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import AsyncOpenAI

import settings
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
            formatted_history = self._format_history_for_analysis(conversation_history)
            analysis_prompt = self._create_analysis_prompt(formatted_history, user_ip)
            
            analysis_result = await self._get_async_llm_result(
                prompt=analysis_prompt,
                system_instruction=settings.APPOINTMENT_ANALYSIS_INSTRUCTIONS
            )
            
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
                if role == 'user':
                    formatted_messages.append(f"CLIENTE: {content}")
                elif role == 'assistant':
                    formatted_messages.append(f"ASISTENTE: {content}")
        
        return "\n".join(formatted_messages)
    
    async def _get_async_llm_result(self, prompt: str, system_instruction: str) -> Dict[str, Any]:
        """Obtiene respuesta del LLM de forma asíncrona"""
        try:
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
            analysis_data = llm_response
            processed_data = {
                "budget_min": self._safe_int(analysis_data.get("budget_min")),
                "budget_max": self._safe_int(analysis_data.get("budget_max")),
                "location": self._safe_str(analysis_data.get("location")),
                "location_description": self._safe_str(analysis_data.get("location_description")),
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
    
    def create_conversation_summary(self, conversation_history: List[Dict[str, Any]], analysis_data: Dict[str, Any]) -> str:
        """
        Crea un resumen detallado de la conversación para el email del equipo de ventas
        """
        try:
            user_messages = [msg for msg in conversation_history if msg.get('role') == 'user']
            assistant_messages = [msg for msg in conversation_history if msg.get('role') == 'assistant']
            
            summary_parts = []
            
            summary_parts.append(f"Cliente ha tenido {len(user_messages)} consultas en la conversación.")
            
            if analysis_data.get('budget_min') or analysis_data.get('budget_max'):
                budget_info = []
                if analysis_data.get('budget_min'):
                    budget_info.append(f"mínimo {analysis_data['budget_min']:,}€")
                if analysis_data.get('budget_max'):
                    budget_info.append(f"máximo {analysis_data['budget_max']:,}€")
                summary_parts.append(f"Presupuesto: {' - '.join(budget_info)}")
            
            if analysis_data.get('location'):
                location_info = f"Ubicación: {analysis_data['location']}"
                if analysis_data.get('location_description'):
                    location_info += f" ({analysis_data['location_description']})"
                summary_parts.append(location_info)
            
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
                summary_parts.append(f"Propiedad: {', '.join(property_info)}")
            
            if analysis_data.get('special_features'):
                features = ', '.join(analysis_data['special_features'])
                summary_parts.append(f"Características: {features}")
            
            if analysis_data.get('quality_preferences'):
                quality = ', '.join(analysis_data['quality_preferences'])
                summary_parts.append(f"Preferencias de calidad: {quality}")
            
            if analysis_data.get('personal_context'):
                summary_parts.append(f"Contexto personal: {analysis_data['personal_context']}")
            
            if analysis_data.get('additional_requirements'):
                summary_parts.append(f"Requisitos adicionales: {analysis_data['additional_requirements']}")
            
            if analysis_data.get('urgency') and analysis_data['urgency'] != 'media':
                summary_parts.append(f"Urgencia: {analysis_data['urgency']}")
            
            if analysis_data.get('client_quotes'):
                quotes = ' | '.join([f'"{quote}"' for quote in analysis_data['client_quotes'][:3]])
                summary_parts.append(f"Frases del cliente: {quotes}")
            
            if analysis_data.get('preferences_summary'):
                summary_parts.append(f"Resumen detallado: {analysis_data['preferences_summary']}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error creando resumen de conversación: {str(e)}")
            return f"Cliente ha tenido {len(conversation_history)} mensajes en la conversación."
