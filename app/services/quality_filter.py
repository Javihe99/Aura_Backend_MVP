import logging
import asyncio
from typing import Dict, List, Optional
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from app.services.ai_parse import get_llm_result
from utils import LLMModel, LLMVersion
import settings

logger = logging.getLogger(__name__)


class PropertyQualityFilter:
    """Filtro de calidad para propiedades inmobiliarias"""
    
    def __init__(self):
        """Inicializa el filtro de calidad"""
        pass
    
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

        has_photos = property_data.get('thumbnail') is not None
        score += 0.15 if has_photos else 0

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
    
    def filter_and_rank_properties(self, properties_df: pd.DataFrame, top_n: int = 50, paraphrase_descriptions: bool = False, max_concurrent: int = 5) -> pd.DataFrame:
        """Filtra y rankea propiedades por calidad con opción de paraphraseo"""
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
        
        # Limitar a top_n antes del paraphraseo
        filtered_df = filtered_df.head(top_n)
        
        logger.info(f"Filtered {len(properties_df)} properties to {len(filtered_df)} high-quality properties")
        
        # Aplicar paraphraseo si se solicita
        if paraphrase_descriptions and not filtered_df.empty:
            logger.info("Applying paraphrase to filtered properties...")
            filtered_df = self.paraphrase_property_descriptions(
                filtered_df, max_concurrent=max_concurrent
            )
        
        return filtered_df

    def _paraphrase_single_description(self, description: str, property_data: Dict) -> str:
        """
        Parafrasea una descripción individual eliminando información de contacto de inmobiliarias
        
        Args:
            description: Descripción original de la propiedad
            property_data: Datos adicionales de la propiedad
            
        Returns:
            str: Descripción parafraseada sin información de contacto
        """
        if not description or len(description.strip()) < 10:
            return description
        
        try:
            # Prompt para parafrasear eliminando información de contacto
            paraphrase_prompt = f"""
            Descripción original: {description}
            """
            
            # Usar la instrucción del sistema desde settings
            result = get_llm_result(
                prompt=paraphrase_prompt,
                llm=LLMModel.OPENAI.value,
                model=LLMVersion.OPENAI_4_1_NANO.value,
                system_instruction=settings.DESCRIPTION_PARAPHRASING_INSTRUCTIONS
            )
            
            paraphrased = result.get('description_paraphrased', '').strip()
            
            # Validar que la respuesta no esté vacía
            if not paraphrased or len(paraphrased) < 10:
                logger.warning(f"Paraphrase result too short, using original: {description[:50]}...")
                return description
            
            logger.debug(f"Paraphrased description: {description[:50]}... -> {paraphrased[:50]}...")
            return paraphrased
            
        except Exception as e:
            logger.error(f"Error paraphrasing description: {e}")
            return description

    def paraphrase_property_descriptions(self, properties_df: pd.DataFrame, max_concurrent: int = 5) -> pd.DataFrame:
        """
        Parafrasea las descripciones de múltiples propiedades usando pandas apply optimizado
        
        Args:
            properties_df: DataFrame con las propiedades
            max_concurrent: Número máximo de tareas concurrentes
            
        Returns:
            pd.DataFrame: DataFrame con descripciones parafraseadas
        """
        if properties_df.empty:
            return properties_df
        
        logger.info(f"Paraphrasing {len(properties_df)} property descriptions with max {max_concurrent} concurrent tasks")
        
        # Crear copia del DataFrame para no modificar el original
        result_df = properties_df.copy()
        
        # Filtrar descripciones que necesitan paraphraseo
        needs_paraphrase = result_df['description'].notna() & (result_df['description'].str.len() >= 10)
        
        if not needs_paraphrase.any():
            logger.info("No descriptions need paraphrasing")
            return result_df
        
        # Aplicar paraphraseo solo a las descripciones que lo necesitan
        def paraphrase_description(description):
            """Parafrasea una descripción individual"""
            try:
                return self._paraphrase_single_description(str(description), {})
            except Exception as e:
                logger.error(f"Error paraphrasing description: {e}")
                return description
        
        # Usar pandas apply con concurrencia controlada
        if max_concurrent > 1:
            # Dividir en chunks para procesamiento concurrente
            chunk_size = max(1, len(result_df) // max_concurrent)
            chunks = [result_df.iloc[i:i + chunk_size] for i in range(0, len(result_df), chunk_size)]
            
            # Procesar chunks concurrentemente
            with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                futures = [executor.submit(self._process_chunk_optimized, chunk, paraphrase_description) for chunk in chunks]
                
                # Recoger resultados
                processed_chunks = []
                for i, future in enumerate(futures):
                    try:
                        processed_chunk = future.result()
                        processed_chunks.append(processed_chunk)
                    except Exception as e:
                        logger.error(f"Error processing chunk {i}: {e}")
                        # En caso de error, usar chunk original
                        processed_chunks.append(chunks[i])
                
                # Concatenar resultados
                result_df = pd.concat(processed_chunks, ignore_index=True) if processed_chunks else result_df
        else:
            # Procesamiento secuencial usando pandas apply
            result_df.loc[needs_paraphrase, 'description_paraphrased'] = result_df.loc[needs_paraphrase, 'description'].apply(paraphrase_description)
        
        logger.info(f"Successfully paraphrased {needs_paraphrase.sum()} property descriptions")
        return result_df
    
    def _process_chunk_optimized(self, chunk_df: pd.DataFrame, func) -> pd.DataFrame:
        """Procesa un chunk del DataFrame de forma optimizada usando pandas"""
        try:
            # Crear copia del chunk
            result_chunk = chunk_df.copy()
            
            # Filtrar descripciones que necesitan paraphraseo en este chunk
            needs_paraphrase = result_chunk['description'].notna() & (result_chunk['description'].str.len() >= 10)
            
            if needs_paraphrase.any():
                # Aplicar función solo a las descripciones que lo necesitan
                result_chunk.loc[needs_paraphrase, 'description_paraphrased'] = result_chunk.loc[needs_paraphrase, 'description'].apply(func)
            
            return result_chunk
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            return chunk_df
