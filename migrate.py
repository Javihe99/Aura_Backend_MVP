#!/usr/bin/env python3
"""
Script de migración para Aura Backend MVP v2.0.0
"""

import os
import shutil
import sys
from pathlib import Path

def backup_old_files():
    """Hace backup de los archivos antiguos"""
    backup_dir = Path("backup_v1")
    backup_dir.mkdir(exist_ok=True)
    
    old_files = [
        "main.py",
        "ai_parse.py",
        "idealista_hook.py",
        "utils.py",
        "settings.py"
    ]
    
    print("📦 Creando backup de archivos antiguos...")
    for file in old_files:
        if Path(file).exists():
            shutil.copy2(file, backup_dir / file)
            print(f"   ✅ Backup de {file}")
    
    print(f"   📁 Backup creado en: {backup_dir}")

def create_new_structure():
    """Crea la nueva estructura de directorios"""
    print("🏗️  Creando nueva estructura de directorios...")
    
    # Crear directorios
    directories = [
        "app",
        "app/models",
        "app/services",
        "tests",
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"   ✅ Creado: {directory}/")

def check_dependencies():
    """Verifica las dependencias necesarias"""
    print("🔍 Verificando dependencias...")
    
    try:
        import fastapi
        print("   ✅ FastAPI")
    except ImportError:
        print("   ❌ FastAPI - Instalar con: pip install fastapi")
    
    try:
        import supabase
        print("   ✅ Supabase")
    except ImportError:
        print("   ❌ Supabase - Instalar con: pip install supabase")
    
    try:
        import openai
        print("   ✅ OpenAI")
    except ImportError:
        print("   ❌ OpenAI - Instalar con: pip install openai")
    
    try:
        import google.generativeai
        print("   ✅ Google Generative AI")
    except ImportError:
        print("   ❌ Google Generative AI - Instalar con: pip install google-generativeai")

def create_env_file():
    """Crea el archivo .env si no existe"""
    env_file = Path(".env")
    env_example = Path("env.example")
    
    if not env_file.exists() and env_example.exists():
        print("📝 Creando archivo .env desde env.example...")
        shutil.copy2(env_example, env_file)
        print("   ✅ Archivo .env creado")
        print("   ⚠️  Recuerda editar .env con tus claves de API")
    elif env_file.exists():
        print("   ✅ Archivo .env ya existe")
    else:
        print("   ⚠️  No se encontró env.example")

def print_migration_steps():
    """Imprime los pasos de migración"""
    print("\n🚀 Pasos de migración completados!")
    print("\n📋 Próximos pasos:")
    print("1. Editar archivo .env con tus claves de API")
    print("2. Configurar Supabase (opcional, para memoria)")
    print("3. Instalar dependencias: pip install -r requirements.txt")
    print("4. Ejecutar: python start.py")
    print("\n🔗 Documentación disponible en:")
    print("   - README.md")
    print("   - http://localhost:8000/docs (cuando ejecutes el servidor)")
    
    print("\n⚠️  Notas importantes:")
    print("   - Los endpoints legacy (/new_prompt, /new_maps) siguen funcionando")
    print("   - Se recomienda migrar a los nuevos endpoints (/chat, /maps)")
    print("   - El backup está disponible en la carpeta 'backup_v1'")

def main():
    """Función principal de migración"""
    print("🔄 Migración a Aura Backend MVP v2.0.0")
    print("=" * 50)
    
    # Verificar que estamos en el directorio correcto
    if not Path("main.py").exists():
        print("❌ Error: No se encontró main.py")
        print("   Ejecuta este script desde el directorio raíz del proyecto")
        sys.exit(1)
    
    try:
        backup_old_files()
        create_new_structure()
        check_dependencies()
        create_env_file()
        print_migration_steps()
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        print("   Revisa los logs y contacta con soporte")
        sys.exit(1)

if __name__ == "__main__":
    main()







