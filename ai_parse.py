# pip install openai
import os
import json
import logging
import google.generativeai as genai
from utils import LLMModel
from utils import LLMVersion
from dotenv import load_dotenv
from openai import OpenAI
import settings

load_dotenv()
print(os.getenv('GOOGLE_API_KEY'))
logging.info("Google API Key loaded" + str(os.getenv('GOOGLE_API_KEY')))
import logging

logging.basicConfig(level=logging.INFO)


def get_llm_result(prompt: str, llm=LLMModel.OPENAI, model=LLMVersion.OPENAI_4_1_NANO,
                   system_instruction=settings.IDEALISTA_SYSTEM_INSTRUCTIONS, validate_location: bool = True) -> dict:
    """
    Obtiene una respuesta de un modelo de lenguaje (OpenAI o Gemini)

    Args:
        prompt: El prompt del usuario
        llm: El modelo de LLM a usar (OPENAI o GEMINI)
        model: La versión específica del modelo
        system_instruction: Instrucciones del sistema
        validate_location: Si validar la ubicación

    Returns:
        dict: Respuesta parseada como JSON
    """
    try:
        # Extraer el valor string de las enumeraciones
        model_value = model.value if hasattr(model, 'value') else str(model)
        llm_value = llm.value if hasattr(llm, 'value') else str(llm)

        if llm == LLMModel.OPENAI:
            return _get_openai_result(prompt, model_value, system_instruction)
        elif llm == LLMModel.GEMINI:
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


if __name__ == "__main__":
    texto = "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000 €"

    # Probar con OpenAI
    try:
        print("=== Probando con OpenAI ===")
        data_openai = get_llm_result(texto, llm=LLMModel.OPENAI, model=LLMVersion.OPENAI_5_NANO)
        print(json.dumps(data_openai, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error con OpenAI: {e}")

    # Probar con Gemini
    try:
        print("\n=== Probando con Gemini ===")
        data_gemini = get_llm_result(texto, llm=LLMModel.GEMINI, model=LLMVersion.GEMINI_2_0_FLASH_EXP)
        print(json.dumps(data_gemini, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error con Gemini: {e}")