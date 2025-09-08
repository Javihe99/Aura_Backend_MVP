# pip install openai
import os
import json
import logging
import google.generativeai as genai

from settings import LOCATION_VALIDATION_PROMPT
from utils import LLMModel
from utils import LLMVersion
from dotenv import load_dotenv
from openai import OpenAI
import settings

load_dotenv()
logging.info("Google API Key loaded: " + str(bool(os.getenv('GOOGLE_API_KEY'))))
logging.basicConfig(level=logging.INFO)


# Location validation system prompt

def validate_and_correct_location(location_name: str, default_city, llm=LLMModel.OPENAI.value,
                                  model=LLMVersion.OPENAI_4_1_NANO.value, ) -> dict:
    """
        Propósito: Valida y corrige nombres de ubicaciones usando IA
        Soporta: OpenAI y Gemini
        Funcionalidad: Antes de hacer geocoding, usa IA para corregir nombres de lugares mal escritos
        Fallback: Si falla, devuelve la ciudad por defecto
    """
    try:
        if llm == LLMModel.OPENAI.value:
            return _validate_location_openai(location_name, model)
        elif llm == LLMModel.GEMINI.value:
            return _validate_location_gemini(location_name, model)
        else:
            raise ValueError(f"Modelo LLM no soportado para validación: {llm}")
    except Exception as e:
        logging.error(f"Error en validación de ubicación: {str(e)}")
        # Return fallback
        return {
            "original_location": location_name,
            "corrected_location": default_city,
            "confidence": 0.1,
            "reason": f"Error en validación: {str(e)}",
            "location_type": "fallback"
        }


def _validate_location_openai(location_name: str, model: str) -> dict:
    """Validate location using OpenAI"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        full_prompt = f"""Ubicación a validar: {location_name}
        Responde en formato JSON válido.
        """
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": LOCATION_VALIDATION_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        result = response.choices[0].message.content
        logging.info(f"Location validation OpenAI response: {result}")
        return json.loads(result)

    except Exception as e:
        logging.error(f"Error en validación OpenAI: {str(e)}")
        raise


def _validate_location_gemini(location_name: str, model: str) -> dict:
    """Validate location using Gemini"""
    try:
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

        gemini_model = genai.GenerativeModel(
            model_name=model,
            generation_config=genai.GenerationConfig(
                temperature=0,
                response_mime_type="application/json",
            )
        )

        full_prompt = f"""
        {LOCATION_VALIDATION_PROMPT}
        
        Ubicación a validar: {location_name}
        """

        response = gemini_model.generate_content(full_prompt)
        result = response.candidates[0].content.parts[0].text
        logging.info(f"Location validation Gemini response: {result}")
        return json.loads(result)

    except Exception as e:
        logging.error(f"Error en validación Gemini: {str(e)}")
        raise


def get_llm_result(prompt: str, llm=LLMModel.OPENAI.value, model=LLMVersion.OPENAI_4_1_NANO.value,
                   system_instruction=settings.IDEALISTA_SYSTEM_INSTRUCTIONS) -> dict:
    """
        Propósito: Función principal para obtener información parseada a partir de un prompt usando LLM
        Soporta: OpenAI y Gemini
        Parámetros: prompt, modelo, instrucciones del sistema
        Retorna: JSON parseado con la respuesta

    Args:
        prompt: El prompt del usuario
        llm: El modelo de LLM a usar (OPENAI o GEMINI)
        model: La versión específica del modelo
        system_instruction: Instrucciones del sistema

    Returns:
        dict: Respuesta parseada como JSON
    """
    try:
        # Extraer el valor string de las enumeraciones
        model_value = model.value if hasattr(model, 'value') else str(model)
        llm_value = llm.value if hasattr(llm, 'value') else str(llm)

        if llm == LLMModel.OPENAI.value:
            return _get_openai_result(prompt, model_value, system_instruction)
        elif llm == LLMModel.GEMINI.value:
            return _get_gemini_result(prompt, model_value, system_instruction)
        else:
            raise ValueError(f"Modelo LLM no soportado: {llm_value}")
    except Exception as e:
        logging.error(f"Error al obtener respuesta del LLM: {str(e)}")
        raise


def _get_openai_result(prompt: str, model: str, system_instruction: str) -> dict:
    """Obtiene respuesta de OpenAI"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # FIXED: Add "json" to the user message to comply with OpenAI requirements
        full_prompt = f"""
        Usuario: {prompt}

        Por favor, responde en formato JSON válido.
        """

        response = client.chat.completions.create(
            model=model,
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
        logging.error(f"Error en OpenAI: {str(e)}")
        raise


def _get_gemini_result(prompt: str, model: str, system_instruction: str) -> dict:
    """Obtiene respuesta de Gemini"""
    try:
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

        # Configurar el modelo Gemini
        gemini_model = genai.GenerativeModel(
            model_name=model,
            generation_config=genai.GenerationConfig(
                temperature=0,
                response_mime_type="application/json",
            )
        )

        # Para Gemini, incluimos las instrucciones del sistema en el prompt
        full_prompt = f"""
        {system_instruction}

        Usuario: {prompt}
        """

        response = gemini_model.generate_content(full_prompt)
        result = response.candidates[0].content.parts[0].text
        logging.info(f"Gemini Response: {result}")
        return json.loads(result)

    except Exception as e:
        logging.error(f"Error en Gemini: {str(e)}")
        raise


def get_property_summary_llm(properties: list, search_params: dict, conversation_context: str = "") -> str:
    """
    Genera un resumen de propiedades usando LLM
    
    Args:
        properties: Lista de propiedades encontradas
        search_params: Parámetros de búsqueda utilizados
        conversation_context: Contexto de la conversación previa
        
    Returns:
        str: Resumen generado por el LLM
    """
    try:
        if not properties:
            return "No se encontraron propiedades que cumplan con los criterios especificados."

        # Preparar información de las 3 mejores propiedades
        top_properties = properties[:3]
        properties_info = []

        for i, prop in enumerate(top_properties, 1):
            info = f"Propiedad {i}: "
            info += f"{prop.get('rooms', 'N/A')} hab, "
            info += f"{prop.get('size', 'N/A')}m², "
            info += f"{prop.get('price', 'N/A')}€"

            if prop.get('address'):
                info += f", en {prop.get('address')}"

            price_per_m2 = prop.get('priceByArea')
            if price_per_m2:
                info += f" ({price_per_m2:.0f}€/m²)"

            properties_info.append(info)

        # Crear prompt para el resumen
        prompt = f"""
        Contexto de conversación:
        {conversation_context}
        
        Se encontraron {len(properties)} propiedades. Las 3 más relevantes son:
        {'. '.join(properties_info)}
        
        Genera un resumen conciso (máximo 3 líneas) destacando:
        1. Número total de propiedades encontradas
        2. Rango de precios
        3. Características destacadas de las mejores opciones
        
        Responde en formato JSON con la clave "summary".
        """

        result = get_llm_result(prompt)
        return result.get('summary', 'Se encontraron propiedades interesantes según tus criterios.')

    except Exception as e:
        logging.error(f"Error generating property summary: {e}")
        # Fallback manual si falla el LLM
        return _generate_fallback_summary(properties, top_properties)


def _generate_fallback_summary(properties: list, top_properties: list) -> str:
    """Genera un resumen de fallback si falla el LLM"""
    if not top_properties:
        return f"Se encontraron {len(properties)} propiedades."

    try:
        # Calcular rango de precios
        prices = [p.get('price', 0) for p in top_properties if p.get('price')]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0

        # Obtener características destacadas
        rooms = [p.get('rooms') for p in top_properties if p.get('rooms')]
        avg_rooms = sum(rooms) / len(rooms) if rooms else 0

        summary = f"Se encontraron {len(properties)} propiedades. "
        if min_price > 0 and max_price > 0:
            summary += f"Las mejores opciones tienen entre {min_price:,.0f}€ y {max_price:,.0f}€. "

        if avg_rooms > 0:
            summary += f"Promedio de {avg_rooms:.1f} habitaciones en las mejores opciones."

        return summary

    except Exception as e:
        logging.error(f"Error in fallback summary: {e}")
        return f"Se encontraron {len(properties)} propiedades según tus criterios de búsqueda."


if __name__ == "__main__":
    texto = "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000 €"

    # Probar con OpenAI
    try:
        print("=== Probando con OpenAI ===")
        data_openai = get_llm_result(texto, llm=LLMModel.OPENAI.value, model=LLMVersion.OPENAI_5_NANO.value)
        print(json.dumps(data_openai, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error con OpenAI: {e}")

    # Probar con Gemini
    try:
        print("\n=== Probando con Gemini ===")
        data_gemini = get_llm_result(texto, llm=LLMModel.GEMINI.value, model=LLMVersion.GEMINI_2_0_FLASH_EXP.value)
        print(json.dumps(data_gemini, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error con Gemini: {e}")




