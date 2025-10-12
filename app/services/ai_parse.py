import json
import logging
import os

import google.generativeai as genai
from dotenv import load_dotenv
from openai import OpenAI

import settings
from utils import LLMModel
from utils import LLMVersion

load_dotenv()
logging.info("Google API Key loaded: " + str(bool(os.getenv('GOOGLE_API_KEY'))))
logging.basicConfig(level=logging.INFO)

def validate_and_correct_location(location_name: str, default_city, llm=LLMModel.OPENAI.value,
                                  model=LLMVersion.OPENAI_4_1_NANO.value, ) -> dict:
    """
    Valida y corrige nombres de ubicaciones usando IA.
    Soporta OpenAI y Gemini.
    Si falla, devuelve la ciudad por defecto.
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
        return {
            "original_location": location_name,
            "corrected_location": default_city,
            "confidence": 0.1,
            "reason": f"Error en validación: {str(e)}",
            "location_type": "fallback"
        }


def _validate_location_openai(location_name: str, model: str) -> dict:
    """Valida ubicación usando OpenAI"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        full_prompt = f"""Ubicación a validar: {location_name}
        Responde en formato JSON válido.
        """
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": settings.LOCATION_VALIDATION_PROMPT},
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
    """Valida ubicación usando Gemini"""
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
        {settings.LOCATION_VALIDATION_PROMPT}
        
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
    Función principal para obtener información parseada a partir de un prompt usando LLM.
    Soporta OpenAI y Gemini.
    
    Args:
        prompt: El prompt del usuario
        llm: El modelo de LLM a usar (OPENAI o GEMINI)
        model: La versión específica del modelo
        system_instruction: Instrucciones del sistema

    Returns:
        dict: Respuesta parseada como JSON
    """
    try:
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

    suggestions.extend([
        "• Considerar propiedades en zonas cercanas",
        "• Revisar si hay propiedades similares con características ligeramente diferentes",
        "• Contactar con un agente inmobiliario para búsquedas personalizadas"
    ])

    return "Te sugiero:\n" + "\n".join(suggestions[:4])


if __name__ == "__main__":
    texto = "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000 €"

    try:
        print("=== Probando con OpenAI ===")
        data_openai = get_llm_result(texto, llm=LLMModel.OPENAI.value, model=LLMVersion.OPENAI_5_NANO.value)
        print(json.dumps(data_openai, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error con OpenAI: {e}")

    try:
        print("\n=== Probando con Gemini ===")
        data_gemini = get_llm_result(texto, llm=LLMModel.GEMINI.value, model=LLMVersion.GEMINI_2_0_FLASH_EXP.value)
        print(json.dumps(data_gemini, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error con Gemini: {e}")


