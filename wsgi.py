import sys
import os

# Append the project directory to the path
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Import the FastAPI app
from app import app

# For PythonAnywhere, we need to create a WSGI application
from fastapi.middleware.wsgi import WSGIMiddleware

# Create a WSGI app wrapper for the FastAPI app
application = WSGIMiddleware(app)
