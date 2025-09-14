"""
Servicio para analizar el historial de conversaciones y extraer información relevante para citas
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import openai
from app.config import Config

logger = logging.getLogger(__name__)

class AppointmentAnalyzer:
    """Analizador de conversaciones para extraer información relevante para citas"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
    
    async def analyze_conversation_history(self, conversation_history: List[Dict[str, Any]], user_ip: str = None) -> Dict[str, Any]:
        """
        Analiza el historial de conversación para extraer información relevante
        
        Args:
            conversation_history: Lista de mensajes de la conversación
            user_ip: IP del usuario para detectar ubicación
            
        Returns:
            Dict con información extraída: budget_min, budget_max, location, financing, metadata
        """
        try:
            # Formatear historial para el LLM
            formatted_history = self._format_history_for_analysis(conversation_history)
            
            # Crear prompt para análisis
            analysis_prompt = self._create_analysis_prompt(formatted_history, user_ip)
            
            # Llamar al LLM para análisis
            analysis_result = await self._call_llm_for_analysis(analysis_prompt)
            
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
    
    def _create_analysis_prompt(self, formatted_history: str, user_ip: str = None) -> str:
        """Crea el prompt para el análisis del LLM"""
        
        ip_context = ""
        if user_ip:
            ip_context = f"\n\nIP del usuario: {user_ip} (puede ayudar a determinar ubicación geográfica)"
        
        prompt = f"""
Eres un experto analista de conversaciones inmobiliarias. Tu tarea es analizar el historial de conversación de un cliente y extraer información clave para una cita inmobiliaria.

HISTORIAL DE CONVERSACIÓN:
{formatted_history}
{ip_context}

IMPORTANTE: 
- USER = Cliente (lo que dice el cliente)
- ASSISTANT = Asistente inmobiliario (respuestas del sistema)
- SOLO analiza lo que dice el CLIENTE (USER), ignora las respuestas del asistente
- NO uses presupuestos, precios o información que mencione el ASSISTANT
- FOCÚSATE únicamente en las necesidades, preferencias y presupuesto del CLIENTE

INSTRUCCIONES:
Analiza cuidadosamente SOLO los mensajes del CLIENTE (USER) y extrae la siguiente información:

1. PRESUPUESTO (solo del cliente):
   - Presupuesto mínimo mencionado por el CLIENTE (budget_min)
   - Presupuesto máximo mencionado por el CLIENTE (budget_max)
   - Si el cliente menciona rangos como "entre X e Y", extrae ambos valores
   - Si el cliente solo menciona "máximo X" o "hasta X", usa ese como budget_max
   - Si el cliente solo menciona "mínimo X" o "desde X", usa ese como budget_min
   - IGNORA cualquier precio o presupuesto mencionado por el ASSISTANT

2. UBICACIÓN (solo del cliente):
   - Localización específica mencionada por el CLIENTE (ciudad, barrio, zona)
   - Preferencias de ubicación expresadas por el CLIENTE
   - Si no se menciona ubicación específica, intenta inferirla del contexto

3. FINANCIACIÓN (solo del cliente):
   - Si el CLIENTE menciona necesidad de financiación, hipoteca, préstamo
   - Si el CLIENTE pregunta sobre opciones de pago
   - Si el CLIENTE menciona ser primera vivienda (puede necesitar financiación)

4. CARACTERÍSTICAS ESPECÍFICAS (solo del cliente):
   - Tipo de propiedad mencionado por el CLIENTE (piso, casa, apartamento, etc.)
   - Número de habitaciones solicitado por el CLIENTE
   - Características especiales mencionadas por el CLIENTE (garaje, terraza, jardín, etc.)
   - Preferencias de estado expresadas por el CLIENTE (nuevo, reformado, etc.)

5. CONTEXTO PERSONAL (solo del cliente):
   - Situación familiar mencionada por el CLIENTE (pareja, hijos, etc.)
   - Motivo de compra expresado por el CLIENTE (primera vivienda, inversión, etc.)
   - Urgencia o timeline mencionado por el CLIENTE

FORMATO DE RESPUESTA (JSON):
{{
    "budget_min": null o número entero,
    "budget_max": null o número entero,
    "location": "ubicación mencionada o inferida",
    "financing": true/false,
    "property_type": "tipo de propiedad mencionado",
    "bedrooms": null o número,
    "special_features": ["lista", "de", "características"],
    "personal_context": "contexto personal relevante",
    "urgency": "alta/media/baja",
    "preferences_summary": "resumen de preferencias principales"
}}

IMPORTANTE:
- Si no se menciona algo específico, usa null para números y "" para strings
- Sé conservador en las inferencias
- Prioriza información explícita sobre inferida
- Para financing, solo marca true si es explícitamente mencionado
"""
        
        return prompt
    
    async def _call_llm_for_analysis(self, prompt: str) -> str:
        """Llama al LLM para realizar el análisis"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Eres un experto analista de conversaciones inmobiliarias. Responde ÚNICAMENTE con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error llamando al LLM para análisis: {str(e)}")
            raise
    
    def _process_analysis_result(self, llm_response: str) -> Dict[str, Any]:
        """Procesa y valida el resultado del LLM"""
        try:
            # Limpiar respuesta del LLM
            cleaned_response = llm_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            # Parsear JSON
            analysis_data = json.loads(cleaned_response)
            
            # Validar y limpiar datos
            processed_data = {
                "budget_min": self._safe_int(analysis_data.get("budget_min")),
                "budget_max": self._safe_int(analysis_data.get("budget_max")),
                "location": analysis_data.get("location", "").strip() or None,
                "financing": bool(analysis_data.get("financing", False)),
                "property_type": analysis_data.get("property_type", "").strip() or None,
                "bedrooms": self._safe_int(analysis_data.get("bedrooms")),
                "special_features": analysis_data.get("special_features", []),
                "personal_context": analysis_data.get("personal_context", "").strip() or None,
                "urgency": analysis_data.get("urgency", "media").strip().lower(),
                "preferences_summary": analysis_data.get("preferences_summary", "").strip() or None
            }
            
            return processed_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON del LLM: {str(e)}")
            logger.error(f"Respuesta del LLM: {llm_response}")
            return self._get_default_analysis()
        except Exception as e:
            logger.error(f"Error procesando resultado del análisis: {str(e)}")
            return self._get_default_analysis()
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Convierte valor a int de forma segura"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _get_default_analysis(self) -> Dict[str, Any]:
        """Retorna análisis por defecto en caso de error"""
        return {
            "budget_min": None,
            "budget_max": None,
            "location": None,
            "financing": False,
            "property_type": None,
            "bedrooms": None,
            "special_features": [],
            "personal_context": None,
            "urgency": "media",
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
        Crea un resumen de la conversación para el email
        
        Args:
            conversation_history: Historial de conversación
            analysis_data: Datos extraídos del análisis
            
        Returns:
            Resumen formateado de la conversación
        """
        try:
            # Contar mensajes
            user_messages = [msg for msg in conversation_history if msg.get('role') == 'user']
            assistant_messages = [msg for msg in conversation_history if msg.get('role') == 'assistant']
            
            # Crear resumen
            summary_parts = []
            
            # Información básica
            summary_parts.append(f"Cliente ha tenido {len(user_messages)} consultas en la conversación.")
            
            # Presupuesto
            if analysis_data.get('budget_min') or analysis_data.get('budget_max'):
                budget_info = []
                if analysis_data.get('budget_min'):
                    budget_info.append(f"mínimo {analysis_data['budget_min']:,}€")
                if analysis_data.get('budget_max'):
                    budget_info.append(f"máximo {analysis_data['budget_max']:,}€")
                summary_parts.append(f"Presupuesto: {' - '.join(budget_info)}")
            
            # Ubicación
            if analysis_data.get('location'):
                summary_parts.append(f"Ubicación de interés: {analysis_data['location']}")
            
            # Tipo de propiedad
            if analysis_data.get('property_type'):
                summary_parts.append(f"Tipo de propiedad: {analysis_data['property_type']}")
            
            # Características especiales
            if analysis_data.get('special_features'):
                features = ', '.join(analysis_data['special_features'])
                summary_parts.append(f"Características deseadas: {features}")
            
            # Financiación
            if analysis_data.get('financing'):
                summary_parts.append("Necesita financiación/hipoteca")
            
            # Contexto personal
            if analysis_data.get('personal_context'):
                summary_parts.append(f"Contexto: {analysis_data['personal_context']}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error creando resumen de conversación: {str(e)}")
            return f"Cliente ha tenido {len(conversation_history)} mensajes en la conversación."
