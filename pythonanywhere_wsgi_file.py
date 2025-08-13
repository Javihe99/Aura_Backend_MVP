# WSGI configuration for PythonAnywhere
import sys
import os

# Add your project directory to Python path
username = 'javihe99'  # Replace with your actual username
project_path = f'/home/{username}/Aura_Backend_MVP'
if project_path not in sys.path:
    sys.path.append(project_path)

# Import your application
from wsgi import application
