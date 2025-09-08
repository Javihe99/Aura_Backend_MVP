import logging
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


class PropertyQualityFilter:
    """Filtro de calidad para propiedades inmobiliarias"""
    
    @staticmethod
    def calculate_quality_score(property_data: Dict) -> float:
        """Calcula un score de calidad para una propiedad"""
        score = 0.0
        
        # Precio por m² (más importante)
        price_per_m2 = property_data.get('priceByArea', 0)
        if price_per_m2 > 0:
            # Normalizar precio por m² (asumiendo rango 1000-10000 €/m²)
            normalized_price = 1 - min(price_per_m2 / 10000, 1)
            score += normalized_price * 0.3
        
        # Fotos disponibles
        has_photos = property_data.get('thumbnail') is not None
        score += 0.15 if has_photos else 0
        
        # Descripción completa
        description = property_data.get('description', '') or ''
        if len(description) > 100:
            score += 0.1
        
        # Estado de la propiedad
        status = property_data.get('additional_info_name', '')
        if not status or status == 'Disponible':
            score += 0.2
        elif status in ['Alquilada', 'Nuda propiedad']:
            score -= 0.1
        elif status == 'Ocupada ilegalmente':
            score -= 0.3
        
        # Características extras
        if property_data.get('hasLift'):
            score += 0.05
        if property_data.get('exterior'):
            score += 0.05
        if property_data.get('parkingSpace'):
            score += 0.1
        if property_data.get('hasAirConditioning'):
            score += 0.05
        
        # Año de construcción (si está disponible)
        built_year = property_data.get('builtYear')
        if built_year:
            try:
                age = 2025 - int(built_year)
                if age < 10:
                    score += 0.1
                elif age > 50:
                    score -= 0.05
            except (ValueError, TypeError):
                pass
        
        # Ubicación (si está disponible)
        if property_data.get('address'):
            address = property_data.get('address', '').lower()
            # Penalizar ubicaciones problemáticas
            if any(word in address for word in ['industrial', 'polígono', 'nave']):
                score -= 0.1
        
        return min(max(score, 0), 1)  # Normalizar entre 0 y 1
    
    @staticmethod
    def filter_and_rank_properties(properties_df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
        """Filtra y rankea propiedades por calidad"""
        if properties_df.empty:
            return properties_df
        
        # Calcular score de calidad para cada propiedad
        properties_df['quality_score'] = properties_df.apply(
            lambda row: PropertyQualityFilter.calculate_quality_score(row.to_dict()), 
            axis=1
        )
        
        # Filtrar propiedades con score mínimo
        min_quality_threshold = 0.3
        filtered_df = properties_df[properties_df['quality_score'] >= min_quality_threshold]
        
        # Si no hay suficientes propiedades de calidad, bajar el threshold
        if len(filtered_df) < 10:
            min_quality_threshold = 0.2
            filtered_df = properties_df[properties_df['quality_score'] >= min_quality_threshold]
        
        # Si aún no hay suficientes, usar todas pero ordenadas por calidad
        if len(filtered_df) < 5:
            filtered_df = properties_df.copy()
        
        # Ordenar por score de calidad y precio por m²
        filtered_df = filtered_df.sort_values(
            by=['quality_score', 'priceByArea'], 
            ascending=[False, True]
        )
        
        logger.info(f"Filtered {len(properties_df)} properties to {len(filtered_df)} high-quality properties")
        return filtered_df.head(top_n)




