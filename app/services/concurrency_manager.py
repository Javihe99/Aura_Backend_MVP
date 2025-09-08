import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class RequestLimiter:
    """Limitador de solicitudes concurrentes"""
    
    def __init__(self, max_concurrent: int = 5, rate_limit_per_minute: int = 60):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_requests: Dict[str, datetime] = {}
        self.rate_limit_per_minute = rate_limit_per_minute
        self.request_history: Dict[str, list] = {}
        
    async def acquire(self, session_id: str):
        """Adquiere permiso para procesar una solicitud"""
        async with self.semaphore:
            # Verificar rate limiting
            if not self._check_rate_limit(session_id):
                raise HTTPException(
                    status_code=429, 
                    detail="Demasiadas solicitudes. Intenta de nuevo en un minuto."
                )
            
            # Evitar solicitudes duplicadas por sesión
            if session_id in self.active_requests:
                # Verificar si la solicitud anterior es muy reciente (menos de 5 segundos)
                time_diff = datetime.now() - self.active_requests[session_id]
                if time_diff < timedelta(seconds=5):
                    raise HTTPException(
                        status_code=429, 
                        detail="Solicitud en proceso para esta sesión. Espera unos segundos."
                    )
            
            self.active_requests[session_id] = datetime.now()
            self._add_request_to_history(session_id)
            return True
    
    def release(self, session_id: str):
        """Libera el permiso de solicitud"""
        if session_id in self.active_requests:
            del self.active_requests[session_id]
    
    def _check_rate_limit(self, session_id: str) -> bool:
        """Verifica el rate limiting por sesión"""
        now = datetime.now()
        if session_id not in self.request_history:
            self.request_history[session_id] = []
        
        # Limpiar solicitudes antiguas (más de 1 minuto)
        self.request_history[session_id] = [
            req_time for req_time in self.request_history[session_id]
            if now - req_time < timedelta(minutes=1)
        ]
        
        # Verificar si no excede el límite
        return len(self.request_history[session_id]) < self.rate_limit_per_minute
    
    def _add_request_to_history(self, session_id: str):
        """Añade una solicitud al historial"""
        if session_id not in self.request_history:
            self.request_history[session_id] = []
        
        self.request_history[session_id].append(datetime.now())
    
    def get_active_requests_count(self) -> int:
        """Obtiene el número de solicitudes activas"""
        return len(self.active_requests)
    
    def get_session_stats(self, session_id: str) -> Dict:
        """Obtiene estadísticas de una sesión específica"""
        if session_id not in self.request_history:
            return {"total_requests": 0, "recent_requests": 0}
        
        now = datetime.now()
        recent_requests = len([
            req_time for req_time in self.request_history[session_id]
            if now - req_time < timedelta(minutes=1)
        ])
        
        return {
            "total_requests": len(self.request_history[session_id]),
            "recent_requests": recent_requests,
            "is_active": session_id in self.active_requests
        }
    
    async def cleanup_old_requests(self):
        """Limpia solicitudes antiguas del historial"""
        now = datetime.now()
        cutoff_time = now - timedelta(hours=1)
        
        for session_id in list(self.request_history.keys()):
            self.request_history[session_id] = [
                req_time for req_time in self.request_history[session_id]
                if req_time > cutoff_time
            ]
            
            # Eliminar sesiones sin solicitudes recientes
            if not self.request_history[session_id]:
                del self.request_history[session_id]
        
        logger.info(f"Cleaned up old requests. Active sessions: {len(self.request_history)}")


class AsyncTaskManager:
    """Gestor de tareas asíncronas"""
    
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.max_concurrent_tasks = 10
    
    async def add_task(self, task_id: str, coro, background: bool = True):
        """Añade una nueva tarea"""
        if len(self.tasks) >= self.max_concurrent_tasks:
            # Cancelar la tarea más antigua si es necesario
            oldest_task_id = min(self.tasks.keys(), key=lambda k: self.tasks[k].created_at)
            await self.cancel_task(oldest_task_id)
        
        if background:
            task = asyncio.create_task(coro)
            task.created_at = datetime.now()
            self.tasks[task_id] = task
        else:
            return await coro
    
    async def cancel_task(self, task_id: str):
        """Cancela una tarea específica"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.tasks[task_id]
    
    async def wait_for_task(self, task_id: str, timeout: float = 30.0):
        """Espera a que una tarea se complete"""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        
        try:
            await asyncio.wait_for(self.tasks[task_id], timeout=timeout)
            result = self.tasks[task_id].result()
            del self.tasks[task_id]
            return result
        except asyncio.TimeoutError:
            await self.cancel_task(task_id)
            raise HTTPException(status_code=408, detail="Task timeout")
    
    def get_task_status(self, task_id: str) -> Dict:
        """Obtiene el estado de una tarea"""
        if task_id not in self.tasks:
            return {"status": "not_found"}
        
        task = self.tasks[task_id]
        return {
            "status": "running" if not task.done() else "completed",
            "created_at": task.created_at.isoformat() if hasattr(task, 'created_at') else None,
            "done": task.done(),
            "cancelled": task.cancelled()
        }






