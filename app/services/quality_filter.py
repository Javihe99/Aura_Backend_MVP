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
        pass
    
    @staticmethod
    def calculate_quality_score(property_data: Dict) -> float:
        """Calcula un score de calidad para una propiedad"""
        status = property_data.get('additional_info_name', '')
        score_board={
            'Alquilada': 0,
            'Ocupada ilegalmente': 1,
            'Nuda propiedad': 2,
        }
        return score_board.get(status, 3)
    
    def filter_and_rank_properties(self, properties_df: pd.DataFrame, top_n: int = 50, paraphrase_descriptions: bool = False, max_concurrent: int = 5) -> pd.DataFrame:
        """Filtra y rankea propiedades por calidad con opción de paraphraseo"""
        if properties_df.empty:
            return properties_df
        
        properties_df['quality_score'] = properties_df.apply(
            lambda row: PropertyQualityFilter.calculate_quality_score(row.to_dict()), 
            axis=1
        )

        filtered_df = properties_df.sort_values(
            by=['quality_score', 'priceByArea'], 
            ascending=[False, True]
        )
        
        filtered_df = filtered_df.head(top_n)
        
        logger.info(f"Filtered {len(properties_df)} properties to {len(filtered_df)} high-quality properties")
        
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
            paraphrase_prompt = f"""
            Descripción original: {description}
            """
            
            result = get_llm_result(
                prompt=paraphrase_prompt,
                llm=LLMModel.OPENAI.value,
                model=LLMVersion.OPENAI_4_1_NANO.value,
                system_instruction=settings.DESCRIPTION_PARAPHRASING_INSTRUCTIONS
            )
            
            paraphrased = result.get('description_paraphrased', '').strip()
            
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
        
        result_df = properties_df.copy()
        
        needs_paraphrase = result_df['description'].notna() & (result_df['description'].str.len() >= 10)
        
        if not needs_paraphrase.any():
            logger.info("No descriptions need paraphrasing")
            return result_df
        
        def paraphrase_description(description):
            """Parafrasea una descripción individual"""
            try:
                return self._paraphrase_single_description(str(description), {})
            except Exception as e:
                logger.error(f"Error paraphrasing description: {e}")
                return description
        
        if max_concurrent > 1:
            chunk_size = max(1, len(result_df) // max_concurrent)
            chunks = [result_df.iloc[i:i + chunk_size] for i in range(0, len(result_df), chunk_size)]
            
            with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                futures = [executor.submit(self._process_chunk_optimized, chunk, paraphrase_description) for chunk in chunks]
                
                processed_chunks = []
                for i, future in enumerate(futures):
                    try:
                        processed_chunk = future.result()
                        processed_chunks.append(processed_chunk)
                    except Exception as e:
                        logger.error(f"Error processing chunk {i}: {e}")
                        processed_chunks.append(chunks[i])
                
                result_df = pd.concat(processed_chunks, ignore_index=True) if processed_chunks else result_df
        else:
            result_df.loc[needs_paraphrase, 'description_paraphrased'] = result_df.loc[needs_paraphrase, 'description'].apply(paraphrase_description)
        
        logger.info(f"Successfully paraphrased {needs_paraphrase.sum()} property descriptions")
        return result_df
    
    def _process_chunk_optimized(self, chunk_df: pd.DataFrame, func) -> pd.DataFrame:
        """Procesa un chunk del DataFrame de forma optimizada usando pandas"""
        try:
            result_chunk = chunk_df.copy()
            
            needs_paraphrase = result_chunk['description'].notna() & (result_chunk['description'].str.len() >= 10)
            
            if needs_paraphrase.any():
                result_chunk.loc[needs_paraphrase, 'description_paraphrased'] = result_chunk.loc[needs_paraphrase, 'description'].apply(func)
            
            return result_chunk
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            return chunk_df
