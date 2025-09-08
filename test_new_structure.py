#!/usr/bin/env python3
"""
Script de prueba para verificar la nueva estructura de Aura Backend MVP
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Prueba las importaciones de los nuevos módulos"""
    print("🧪 Probando importaciones...")
    
    try:
        # Probar importaciones de modelos
        from app.models.schemas import ChatRequest, ChatResponse
        print("   ✅ Modelos importados correctamente")
    except ImportError as e:
        print(f"   ❌ Error importando modelos: {e}")
        return False
    
    try:
        # Probar importaciones de servicios
        from app.services.memory_manager import ConversationMemory
        from app.services.quality_filter import PropertyQualityFilter
        from app.services.property_summarizer import PropertySummarizer
        from app.services.concurrency_manager import RequestLimiter
        print("   ✅ Servicios importados correctamente")
    except ImportError as e:
        print(f"   ❌ Error importando servicios: {e}")
        return False
    
    try:
        # Probar configuración
        from app.config import config
        print("   ✅ Configuración importada correctamente")
    except ImportError as e:
        print(f"   ❌ Error importando configuración: {e}")
        return False
    
    return True

def test_config():
    """Prueba la configuración"""
    print("\n🔧 Probando configuración...")
    
    try:
        from app.config import config
        
        # Verificar configuración básica
        print(f"   Server: {config.HOST}:{config.PORT}")
        print(f"   OpenAI API: {'✅' if config.OPENAI_API_KEY else '❌'}")
        print(f"   Google API: {'✅' if config.GOOGLE_API_KEY else '❌'}")
        print(f"   Supabase: {config.get_supabase_status()}")
        
        # Validar configuración
        config_valid = config.validate()
        print(f"   Configuración válida: {'✅' if config_valid else '❌'}")
        
        return config_valid
        
    except Exception as e:
        print(f"   ❌ Error en configuración: {e}")
        return False

def test_fastapi_app():
    """Prueba la aplicación FastAPI"""
    print("\n🚀 Probando aplicación FastAPI...")
    
    try:
        from app.main import app
        
        # Verificar que la app se creó correctamente
        print(f"   Título: {app.title}")
        print(f"   Versión: {app.version}")
        print(f"   Endpoints: {len(app.routes)}")
        
        # Verificar endpoints principales
        endpoints = [route.path for route in app.routes]
        required_endpoints = ["/", "/chat", "/maps", "/health", "/conversation/{session_id}"]
        
        for endpoint in required_endpoints:
            if endpoint in endpoints or any(endpoint.replace("{", "").replace("}", "") in ep for ep in endpoints):
                print(f"   ✅ Endpoint {endpoint}")
            else:
                print(f"   ❌ Endpoint {endpoint} no encontrado")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en aplicación FastAPI: {e}")
        return False

def test_services():
    """Prueba los servicios principales"""
    print("\n🔧 Probando servicios...")
    
    try:
        from app.services.memory_manager import ConversationMemory
        from app.services.quality_filter import PropertyQualityFilter
        from app.services.property_summarizer import PropertySummarizer
        
        # Probar creación de instancias
        memory = ConversationMemory()
        print("   ✅ ConversationMemory creado")
        
        quality_filter = PropertyQualityFilter()
        print("   ✅ PropertyQualityFilter creado")
        
        summarizer = PropertySummarizer()
        print("   ✅ PropertySummarizer creado")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error en servicios: {e}")
        return False

def main():
    """Función principal de pruebas"""
    print("🧪 Pruebas de Aura Backend MVP v2.0.0")
    print("=" * 50)
    
    tests = [
        ("Importaciones", test_imports),
        ("Configuración", test_config),
        ("Aplicación FastAPI", test_fastapi_app),
        ("Servicios", test_services)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"   ❌ Error en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen de resultados
    print("\n📊 Resumen de pruebas:")
    print("=" * 30)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! La nueva estructura está funcionando correctamente.")
        print("\n🚀 Puedes ejecutar el servidor con:")
        print("   python start.py")
        print("\n📚 La documentación estará disponible en:")
        print("   http://localhost:8000/docs")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa los errores y contacta con soporte.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())






