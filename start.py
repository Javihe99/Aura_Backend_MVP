#!/usr/bin/env python3
"""
Script de inicio para Aura Backend MVP
"""

import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # Cargar variables de entorno
    load_dotenv()
    
    # Configuración del servidor
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8001))
    
    print("🚀 Iniciando Aura Backend MVP...")
    print(f"📍 Servidor: {host}:{port}")
    print(f"📚 Documentación: http://{host}:{port}/docs")
    print(f"🔍 Health Check: http://{host}:{port}/health")
    
    # Iniciar servidor
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )