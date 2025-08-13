#!/usr/bin/env python
"""
Deployment verification script for Aura Backend MVP
Run this after deploying to check if your API is working correctly
"""

import requests
import sys
import json

def check_deployment(base_url):
    """Check if the API deployment is working properly."""
    print(f"Checking deployment at {base_url}...")
    
    # Check health endpoint
    try:
        health_url = f"{base_url}/health"
        print(f"Testing health endpoint: {health_url}")
        health_response = requests.get(health_url)
        health_response.raise_for_status()
        health_data = health_response.json()
        
        if health_data.get("status") == "ok":
            print("✅ Health check passed!")
        else:
            print("❌ Health check failed: Unexpected response")
            print(f"Response: {health_data}")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False
    
    # Check items endpoint
    try:
        items_url = f"{base_url}/items"
        print(f"Testing items endpoint: {items_url}")
        items_response = requests.get(items_url)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        if isinstance(items_data, list) and len(items_data) > 0:
            print("✅ Items endpoint passed!")
            print(f"Found {len(items_data)} items")
        else:
            print("❌ Items endpoint failed: Unexpected response")
            print(f"Response: {items_data}")
            return False
    except Exception as e:
        print(f"❌ Items endpoint failed: {str(e)}")
        return False
    
    # Check documentation endpoints
    try:
        docs_url = f"{base_url}/docs"
        print(f"Testing Swagger docs: {docs_url}")
        docs_response = requests.get(docs_url)
        docs_response.raise_for_status()
        print("✅ Swagger docs available!")
    except Exception as e:
        print(f"❌ Swagger docs check failed: {str(e)}")
        # This is not a critical failure, so we continue
    
    print("\n✅ Deployment verification completed successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        # Default to local development server
        base_url = "http://localhost:8000"
    
    print(f"Aura Backend MVP - Deployment Verification")
    print(f"==========================================\n")
    
    success = check_deployment(base_url)
    
    if success:
        sys.exit(0)
    else:
        print("\n❌ Deployment verification failed!")
        sys.exit(1)
