import json
import logging
from typing import Dict, Any
from openai import OpenAI
from app.config import Config
import settings

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Clasificador de intenciones para determinar si el usuario pregunta sobre propiedades"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.intent_classification_prompt = settings.INTENTION_CLASSIFICATION_INSTRUCTIONS

    async def classify_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """
        Clasifica la intención del mensaje del usuario
        
        Args:
            user_message: Mensaje del usuario
            conversation_context: Contexto de la conversación previa
            
        Returns:
            Dict con la clasificación de intención
        """
        try:
            # Preparar el prompt con contexto si existe
            full_prompt = f"""
                    Contexto de conversación previa:
                    {conversation_context}
                    
                    Mensaje del usuario: {user_message}
                    
                    Clasifica la intención del mensaje del usuario.
            """

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.intent_classification_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = response.choices[0].message.content
            logger.info(f"Intent classification result: {result}")
            
            classification = json.loads(result)
            
            # Validar que la respuesta tenga el formato esperado
            if "intent" not in classification:
                logger.warning("Invalid classification response, defaulting to property_search")
                return {
                    "intent": "property_search",
                    "confidence": 0.5,
                    "reasoning": "Respuesta inválida del clasificador, usando búsqueda de propiedades por defecto"
                }
            
            return classification
            
        except Exception as e:
            logger.error(f"Error in intent classification: {str(e)}")
            # En caso de error, asumir que es búsqueda de propiedades para mantener funcionalidad
            return {
                "intent": "property_search",
                "confidence": 0.3,
                "reasoning": f"Error en clasificación: {str(e)}. Usando búsqueda de propiedades por defecto."
            }


class SeniorRealEstateAgent:
    """Agente senior de inmobiliaria para responder consultas generales"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.senior_agent_prompt = settings.SENIOR_AGENT_INSTRUCTIONS

    async def generate_response(self, user_message: str, conversation_context: str = "") -> str:
        """
        Genera una respuesta como senior de inmobiliaria
        
        Args:
            user_message: Mensaje del usuario
            conversation_context: Contexto de la conversación previa
            
        Returns:
            Respuesta generada por el senior de inmobiliaria
        """
        try:
            # Preparar el prompt con contexto si existe
            full_prompt = f"""
Contexto de conversación previa:
{conversation_context}

Consulta del cliente: {user_message}

Responde como un senior de inmobiliaria con experiencia, proporcionando información útil y consejos profesionales.
"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.senior_agent_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            result = response.choices[0].message.content
            logger.info(f"Senior agent response generated")
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Error generating senior agent response: {str(e)}")
            # Respuesta de fallback
            return f"""Hola, soy un senior de inmobiliaria con más de 15 años de experiencia. 

Me disculpo, pero estoy experimentando algunos problemas técnicos en este momento. 

Para ayudarte mejor con tu consulta sobre el sector inmobiliario, te recomiendo que:

1. **Si es sobre compra/venta**: Contacta con uno de nuestros agentes especializados
2. **Si es sobre financiación**: Consulta con nuestro departamento de hipotecas
3. **Si es sobre documentación**: Nuestro equipo legal puede asesorarte

¿Podrías reformular tu pregunta o contactar directamente con nuestro equipo? Estaremos encantados de ayudarte.

¡Gracias por tu paciencia!"""
