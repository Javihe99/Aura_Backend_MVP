#!/usr/bin/env python3
"""
Test script para verificar la nueva estructura de base de datos
"""

import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.memory_manager import ConversationMemory
from app.services.property_manager import PropertyManager

async def test_new_structure():
    """Test la nueva estructura de base de datos"""
    print("🧪 Testing New Database Structure")
    print("=" * 50)
    
    # Initialize managers
    memory_manager = ConversationMemory()
    property_manager = PropertyManager()
    
    if not memory_manager.supabase or not property_manager.supabase:
        print("❌ Supabase not connected")
        return False
    
    test_session_id = "test_new_structure_123"
    test_ip = "192.168.1.100"
    
    try:
        # Test 1: Crear sesión y conversación
        print("1. Testing conversations...")
        session_id = await memory_manager.get_or_create_session(test_session_id, test_ip)
        print(f"   ✅ Session created: {session_id}")
        
        # Guardar mensaje de usuario
        await memory_manager.save_message(
            session_id, 
            "user", 
            "Quiero un piso en Madrid",
            {"test": True},
            test_ip
        )
        print("   ✅ User message saved")
        
        # Test 2: Crear propiedad de ejemplo
        print("2. Testing properties...")
        sample_property = {
            "propertyCode": "test_123456",
            "thumbnail": "https://example.com/image.jpg",
            "numPhotos": 5,
            "price": 300000.0,
            "propertyType": "flat",
            "operation": "sale",
            "size": 80.0,
            "rooms": 2,
            "bathrooms": 1,
            "address": "Calle de Prueba, 123",
            "province": "Madrid",
            "municipality": "Madrid",
            "district": "Centro",
            "country": "es",
            "neighborhood": "Sol",
            "locationId": "test_location",
            "latitude": 40.4168,
            "longitude": -3.7038,
            "showAddress": False,
            "url": "https://example.com/property",
            "distance": "100",
            "description": "Piso de prueba para testing",
            "hasVideo": False,
            "status": "good",
            "newDevelopment": False,
            "favourite": False,
            "newProperty": False,
            "hasLift": True,
            "priceByArea": 3750.0,
            "hasPlan": True,
            "has3DTour": False,
            "has360": False,
            "hasStaging": False,
            "ribbons": [],
            "notes": [],
            "topNewDevelopment": False,
            "topPlus": False,
            "topHighlight": False,
            "preferenceHighlight": False,
            "urgentVisualHighlight": False,
            "visualHighlight": False,
            "priceInfo.price.amount": 300000.0,
            "priceInfo.price.currencySuffix": "€",
            "contactInfo.commercialName": "Test Agency",
            "contactInfo.phone1.phoneNumber": "911234567",
            "features.hasSwimmingPool": False,
            "features.hasTerrace": True,
            "features.hasAirConditioning": True,
            "detailedType.typology": "flat",
            "suggestedTexts.subtitle": "Sol, Madrid",
            "suggestedTexts.title": "Piso en Calle de Prueba",
            "multimedia.images": [{"url": "https://example.com/img1.jpg", "tag": "livingRoom"}],
            "status_sort": 0,
            "quality_score": 0.8
        }
        
        # Guardar propiedad
        success = await property_manager.save_properties([sample_property])
        if success:
            print("   ✅ Property saved successfully")
        else:
            print("   ❌ Failed to save property")
            return False
        
        # Test 3: Recuperar propiedad
        print("3. Testing property retrieval...")
        retrieved_property = await property_manager.get_property_by_code("test_123456")
        if retrieved_property:
            print(f"   ✅ Property retrieved: {retrieved_property['propertyCode']}")
            print(f"   📋 Price: {retrieved_property['price']}€")
            print(f"   📋 Size: {retrieved_property['size']}m²")
        else:
            print("   ❌ Failed to retrieve property")
            return False
        
        # Test 4: Guardar conversación con referencia a propiedad
        print("4. Testing conversation with property reference...")
        await memory_manager.save_message(
            session_id,
            "assistant",
            "He encontrado un piso perfecto para ti",
            {"properties_found": 1, "property_list": ["test_123456"]},
            test_ip
        )
        print("   ✅ Assistant message with property reference saved")
        
        # Test 5: Recuperar propiedades por sesión
        print("5. Testing properties by session...")
        session_properties = await property_manager.get_properties_by_session(session_id)
        if session_properties:
            print(f"   ✅ Found {len(session_properties)} properties for session")
        else:
            print("   ❌ No properties found for session")
            return False
        
        # Test 6: Recuperar historial de conversación
        print("6. Testing conversation history...")
        history = await memory_manager.get_conversation_history(session_id)
        if history:
            print(f"   ✅ Retrieved {len(history)} messages")
            for i, msg in enumerate(history, 1):
                print(f"   Message {i}: {msg.get('role')} - {msg.get('content', '')[:50]}...")
        else:
            print("   ❌ No conversation history found")
            return False
        
        print("\n🎉 All tests passed! New structure is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    success = await test_new_structure()
    
    if success:
        print("\n✅ New database structure is ready!")
        print("📋 You can now:")
        print("   - Store conversations with ip_address")
        print("   - Store all property details with propertyCode as primary key")
        print("   - Retrieve properties by session or by property code")
        print("   - Maintain conversation history")
    else:
        print("\n❌ Tests failed. Check the errors above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)