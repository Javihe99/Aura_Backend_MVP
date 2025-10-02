import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client
import os
from app.config import Config

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Gestor de memoria de conversación usando Supabase"""
    
    def __init__(self):
        self.supabase = self._init_supabase()
        self.max_history = 10  # Máximo de mensajes en memoria
        
    def _init_supabase(self) -> Optional[Client]:
        """Inicializa la conexión con Supabase"""
        try:
            supabase_url = Config.SUPABASE_URL
            supabase_key = Config.get_supabase_key()
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not found. Memory will be disabled.")
                return None
                
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            logger.error(f"Error initializing Supabase: {e}")
            return None
        
    async def get_or_create_session(self, session_id: Optional[str], ip_address: Optional[str]) -> str:
        """Obtiene o crea una sesión (ahora solo retorna el session_id)"""
        if not self.supabase:
            return session_id or hashlib.md5(str(datetime.now()).encode()).hexdigest()
            
        # Si se proporciona un session_id, verificar si existe en conversations
        if session_id:
            try:
                response = self.supabase.table('conversations').select('session_id').eq('session_id', session_id).limit(1).execute()
                if response.data and len(response.data) > 0:
                    # La sesión existe en conversations
                    logger.info(f"Session {session_id} found in conversations")
                    return session_id
                else:
                    # La sesión no existe, se creará automáticamente al guardar la primera conversación
                    logger.info(f"Session {session_id} not found, will be created with first message")
                    return session_id
            except Exception as e:
                logger.error(f"Error checking session existence: {e}")
                # En caso de error, usar el session_id proporcionado
                return session_id
            
        # Crear nuevo session_id si no se proporcionó
        if not session_id:
            session_id = hashlib.md5(f"{ip_address or 'anon'}_{datetime.now()}".encode()).hexdigest()
            logger.info(f"Generated new session_id: {session_id}")
            
        return session_id
    
    async def get_conversation_history(self, session_id: str) -> List[Dict]:
        """Obtiene el historial de conversación"""
        if not self.supabase:
            return []
            
        try:
            response = self.supabase.table('conversations')\
                .select('*')\
                .eq('session_id', session_id)\
                .order('created_at', desc=False)\
                .limit(self.max_history)\
                .execute()
            
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

    async def add_new_row_db(self, table: str, data: Dict):
        """Agrega una nueva fila a una tabla específica"""
        if not self.supabase:
            return
        try:
            if not 'created_at' in data:
                data['created_at'] = datetime.now().isoformat()
            self.supabase.table(table).insert(data).execute()
        except Exception as e:
            logger.error(f"Error saving message: {e}")
    async def save_message(self, session_id: str, role: str, content: str, metadata: Dict = None, ip_address: str = None):
        """Guarda un mensaje en el historial"""
        if not self.supabase:
            return
            
        try:
            self.supabase.table('conversations').insert({
                'session_id': session_id,
                'ip_address': ip_address,
                'role': role,
                'content': content,
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat()
            }).execute()
            logger.info(f"Message saved for session {session_id}")
        except Exception as e:
            logger.error(f"Error saving message: {e}")
    
    def format_history_for_llm(self, history: List[Dict]) -> str:
        """Formatea el historial para el contexto del LLM"""
        if not history:
            return ""
        
        formatted = "Historial de conversación:\n"
        for msg in history[-5:]:  # Últimos 5 mensajes
            formatted += f"{msg.get('role', 'user')}: {msg.get('content', '')[:200]}\n"
        
        return formatted
