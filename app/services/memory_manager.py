import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client
import os

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Gestor de memoria de conversación usando Supabase"""
    
    def __init__(self):
        self.supabase = self._init_supabase()
        self.max_history = 10  # Máximo de mensajes en memoria
        
    def _init_supabase(self) -> Optional[Client]:
        """Inicializa la conexión con Supabase"""
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not found. Memory will be disabled.")
                return None
                
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            logger.error(f"Error initializing Supabase: {e}")
            return None
        
    async def get_or_create_session(self, session_id: Optional[str], user_id: Optional[str]) -> str:
        """Obtiene o crea una sesión"""
        if not self.supabase:
            return session_id or hashlib.md5(str(datetime.now()).encode()).hexdigest()
            
        if session_id:
            return session_id
            
        # Crear nueva sesión
        session_id = hashlib.md5(f"{user_id or 'anon'}_{datetime.now()}".encode()).hexdigest()
        
        try:
            self.supabase.table('sessions').insert({
                'id': session_id,
                'user_id': user_id,
                'created_at': datetime.now().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            
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
    
    async def save_message(self, session_id: str, role: str, content: str, metadata: Dict = None):
        """Guarda un mensaje en el historial"""
        if not self.supabase:
            return
            
        try:
            self.supabase.table('conversations').insert({
                'session_id': session_id,
                'role': role,
                'content': content,
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat()
            }).execute()
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
