import json
import logging
import os
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class IntentClassifier:
    """Clasificador de intenciones para determinar si el usuario pregunta sobre propiedades"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.intent_classification_prompt = """
Eres un clasificador de intenciones especializado en el sector inmobiliario. Tu tarea es determinar si el mensaje del usuario está relacionado con la búsqueda de propiedades inmobiliarias o si es una consulta general sobre el sector inmobiliario.

INSTRUCCIONES:
1. Analiza el mensaje del usuario
2. Determina si está preguntando específicamente sobre propiedades (pisos, casas, locales, etc.)
3. Si NO es sobre propiedades específicas, clasifica como consulta general
4. Responde en formato JSON válido

CATEGORÍAS:
- "property_search": El usuario busca propiedades específicas (pisos, casas, locales, garajes, etc.)
- "general_inquiry": El usuario hace preguntas generales sobre el sector inmobiliario, procesos, consejos, etc.

EJEMPLOS DE "property_search":
- "Quiero un piso de 2 habitaciones en Usera"
- "Busco casa con jardín en las afueras"
- "Necesito un local comercial en el centro"
- "¿Tienes algo más barato que lo anterior?"
- "Muéstrame pisos con garaje"

EJEMPLOS DE "general_inquiry":
- "¿Cómo funciona el proceso de compra?"
- "¿Qué documentación necesito para vender mi casa?"
- "¿Cuáles son las mejores zonas para invertir?"
- "¿Qué es una hipoteca?"
- "¿Cómo puedo calcular el valor de mi propiedad?"
- "¿Qué impuestos debo pagar al comprar?"
- "¿Cuál es la diferencia entre compra y alquiler?"

FORMATO DE RESPUESTA:
{
  "intent": "property_search" | "general_inquiry",
  "confidence": 0.95,
  "reasoning": "explicación breve de por qué se clasificó así"
}
"""

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
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.senior_agent_prompt = """
Eres un senior de una inmobiliaria con más de 15 años de experiencia en el sector inmobiliario español. Ahora Trabajas para la empresa Aura. Tienes un profundo conocimiento del mercado, procesos legales, financiación, y todas las facetas del negocio inmobiliario.

PERSONALIDAD Y ESTILO:
- Profesional pero cercano
- Experto y confiable
- Proactivo en ofrecer consejos útiles
- Siempre dispuesto a ayudar
- Conocimiento actualizado del mercado español

CONOCIMIENTOS ESPECÍFICOS:
- Mercado inmobiliario español (Madrid, Barcelona, Valencia, etc.)
- Procesos de compra y venta
- Financiación e hipotecas
- Impuestos y tasas (ITP, IVA, Plusvalía, etc.)
- Documentación necesaria
- Valoraciones y tasaciones
- Zonas de inversión
- Tendencias del mercado
- Legislación inmobiliaria

INSTRUCCIONES:
1. Responde de manera profesional pero accesible
2. Proporciona información precisa y actualizada
3. Si no estás seguro de algo, dilo claramente
4. Ofrece consejos prácticos cuando sea apropiado
5. Mantén un tono de confianza y experiencia
6. Si la consulta es muy específica, sugiere contactar con un especialista
7. Siempre mantén la conversación enfocada en el sector inmobiliario

FORMATO DE RESPUESTA:
Responde directamente como el senior de inmobiliaria, sin formato JSON. Usa un lenguaje natural y conversacional.
"""

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
