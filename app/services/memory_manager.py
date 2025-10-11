import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Optional
from app.services.supabase_helper import get_supabase_client

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Gestor de memoria de conversación usando Supabase"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.max_history = 10  # Máximo de mensajes en memoria

    
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
    
    def format_history_for_llm(self, history: List[Dict]) -> str:
        """Formatea el historial para el contexto del LLM"""
        if not history:
            return ""
        
        formatted = "Historial de conversación:\n"
        for msg in history[-self.max_history:]:  # Últimos X mensajes
            formatted += f"{msg.get('role', 'user')}: {msg.get('content', '')[-200:]}\n" #Si hay mucho texto, solo se queda con los últimos 200 caracteres
        
        return formatted

    async def save_message(self, session_id: str, role: str, content: str, metadata: Dict = None,
                           ip_address: str = None):
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