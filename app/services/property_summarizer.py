import logging
from typing import List, Dict
from app.services.ai_parse import get_llm_result

logger = logging.getLogger(__name__)


class PropertySummarizer:
    """Generador de resúmenes de propiedades usando LLM"""

    @staticmethod
    async def generate_summary(properties: List[Dict], first_top_properties: int = 20,
                               conversation_context: str = "") -> str:
        """Genera un resumen de las propiedades encontradas"""
        if not properties:
            return "No se encontraron propiedades que cumplan con los criterios especificados."

        try:
            # Preparar información de las mejores propiedades
            top_properties = properties[:first_top_properties]
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
            
            Se encontraron {len(properties)} propiedades. Las {first_top_properties} más relevantes son:
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
            logger.error(f"Error generating summary: {e}")
            # Fallback manual si falla el LLM
            return PropertySummarizer._generate_fallback_summary(properties, top_properties)

    @staticmethod
    def _generate_fallback_summary(properties: List[Dict], top_properties: List[Dict]) -> str:
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
            logger.error(f"Error in fallback summary: {e}")
            return f"Se encontraron {len(properties)} propiedades según tus criterios de búsqueda."

    @staticmethod
    async def generate_search_summary(search_params: Dict, total_found: int) -> str:
        """Genera un resumen de los parámetros de búsqueda"""
        try:
            summary_parts = []

            if search_params.get('locationName'):
                summary_parts.append(f"Ubicación: {search_params['locationName']}")

            if search_params.get('minPrice') or search_params.get('maxPrice'):
                price_range = []
                if search_params.get('minPrice'):
                    price_range.append(f"desde {search_params['minPrice']:,.0f}€")
                if search_params.get('maxPrice'):
                    price_range.append(f"hasta {search_params['maxPrice']:,.0f}€")
                summary_parts.append(f"Precio: {' '.join(price_range)}")

            if search_params.get('rooms'):
                summary_parts.append(f"Habitaciones: {search_params['rooms']}")

            if search_params.get('size'):
                summary_parts.append(f"Tamaño: {search_params['size']}m²")

            summary = f"Búsqueda: {' | '.join(summary_parts)}. Total encontrado: {total_found} propiedades."
            return summary

        except Exception as e:
            logger.error(f"Error generating search summary: {e}")
            return f"Búsqueda completada. Se encontraron {total_found} propiedades."
