"""
Servicio para gestión de appointments en Supabase
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.services.supabase_helper import get_supabase_client

logger = logging.getLogger(__name__)

class AppointmentManager:
    """Gestor de appointments en Supabase"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        if not self.supabase:
            raise Exception("Supabase credentials not configured")
    
    async def create_appointment(self, appointment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo appointment en la base de datos
        
        Args:
            appointment_data: Datos del appointment
            
        Returns:
            Datos del appointment creado
        """
        try:
            # Preparar datos para inserción
            insert_data = {
                "session_id": appointment_data.get("session_id"),
                "appointment_time": appointment_data.get("appointment_time"),
                "email": appointment_data.get("email"),
                "name": appointment_data.get("name"),
                "phone": appointment_data.get("phone"),
                "property_id": appointment_data.get("property_id"),
                "property_url": appointment_data.get("property_url"),
                "user_ip": appointment_data.get("user_ip"),
                "user_location": appointment_data.get("user_location"),
                "budget_min": appointment_data.get("budget_min"),
                "budget_max": appointment_data.get("budget_max"),
                "need_finance": appointment_data.get("need_finance"),
                "time_searching": appointment_data.get("time_searching"),
                "utms": appointment_data.get("utms", {}),
                "preferences_metadata": appointment_data.get("preferences_metadata"),
                "conversation_summary": appointment_data.get("conversation_summary")
            }
            
            # Insertar en la base de datos
            result = self.supabase.table("appointments").insert(insert_data).execute()
            
            if result.data and len(result.data) > 0:
                appointment = result.data[0]
                logger.info(f"Appointment creado exitosamente: {appointment['id']}")
                return appointment
            else:
                raise Exception("No se pudo crear el appointment")
                
        except Exception as e:
            logger.error(f"Error creando appointment: {str(e)}")
            raise
    
    async def get_appointment_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un appointment por su ID
        
        Args:
            appointment_id: ID del appointment
            
        Returns:
            Datos del appointment o None si no existe
        """
        try:
            result = self.supabase.table("appointments").select("*").eq("id", appointment_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo appointment {appointment_id}: {str(e)}")
            return None
    
    async def get_appointments_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene todos los appointments de una sesión
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Lista de appointments
        """
        try:
            result = self.supabase.table("appointments").select("*").eq("session_id", session_id).order("created_at", desc=True).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error obteniendo appointments para sesión {session_id}: {str(e)}")
            return []

    
    async def delete_appointment(self, appointment_id: str) -> bool:
        """
        Elimina un appointment
        
        Args:
            appointment_id: ID del appointment
            
        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        try:
            result = self.supabase.table("appointments").delete().eq("id", appointment_id).execute()
            
            if result.data:
                logger.info(f"Appointment eliminado exitosamente: {appointment_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error eliminando appointment {appointment_id}: {str(e)}")
            return False
    
    async def get_recent_appointments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene los appointments más recientes
        
        Args:
            limit: Número máximo de appointments a devolver
            
        Returns:
            Lista de appointments recientes
        """
        try:
            result = self.supabase.table("appointments").select("*").order("created_at", desc=True).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Error obteniendo appointments recientes: {str(e)}")
            return []
    
    def format_appointment_for_response(self, appointment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formatea un appointment para la respuesta de la API
        
        Args:
            appointment: Datos del appointment de la base de datos
            
        Returns:
            Datos formateados para la respuesta
        """
        return {
            "appointment_id": appointment.get("id"),
            "session_id": appointment.get("session_id"),
            "appointment_time": appointment.get("appointment_time"),
            "email": appointment.get("email"),
            "name": appointment.get("name"),
            "phone": appointment.get("phone"),
            "property_id": appointment.get("property_id"),
            "property_url": appointment.get("property_url"),
            "user_location": appointment.get("user_location"),
            "budget_min": appointment.get("budget_min"),
            "budget_max": appointment.get("budget_max"),
            "need_finance": appointment.get("need_finance"),
            "time_searching": appointment.get("time_searching"),
            "utms": appointment.get("utms", {}),
            "preferences_metadata": appointment.get("preferences_metadata"),
            "conversation_summary": appointment.get("conversation_summary"),
            "created_at": appointment.get("created_at")
        }
