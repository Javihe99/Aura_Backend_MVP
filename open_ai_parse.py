# pip install openai
import os
import json

import google.generativeai as genai
from dotenv import load_dotenv
import settings

load_dotenv()
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
import logging

logging.basicConfig(level=logging.INFO)


def get_llm_result(prompt: str, model: str = "gemini-2.0-flash-exp",
                   system_instruction=settings.IDEALISTA_SYSTEM_INSTRUCTIONS, validate_location: bool = True) -> str:
    model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_instruction,
        generation_config=genai.GenerationConfig(
            temperature=0,
            response_mime_type="application/json",
        )
    )
    full_prompt = f"""
    Usuario: {prompt}
    """
    response = model.generate_content(full_prompt)
    result = response.candidates[0].content.parts[0].text
    logging.info(f"LLM Response: {result}")
    return json.loads(result)


def check_location_is_Nominatim(input: dict):
    if "locationName" in input:
        model = genai.GenerativeModel(
            model_name=model,
            generation_config=genai.GenerationConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=settings.IDEALISTA_SEARCH_PARAMS_SCHEMA  # Tu esquema JSON
            )
        )
    return False


if __name__ == "__main__":
    texto = "Quiero un piso de 2 habitaciones en Usera con garaje por menos de 200.000 €"
    data = get_llm_result(texto)

    print(json.dumps(data, ensure_ascii=False, indent=2))
