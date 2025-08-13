# Deploying Aura Backend MVP on PythonAnywhere

This guide will walk you through the steps to deploy your FastAPI application on PythonAnywhere.

## Prerequisites

1. A PythonAnywhere account (Free tier works for testing, but you might need a paid account for production)
2. Your project files (app.py, wsgi.py, requirements.txt, etc.)

## Deployment Steps

### 1. Upload Your Code to PythonAnywhere

You have several options:
- Upload a ZIP file through the PythonAnywhere web interface
- Clone from a Git repository
- Use the PythonAnywhere console to fetch your code

#### Using Git (Recommended)

If your code is in a Git repository:

1. Open a Bash console on PythonAnywhere
2. Navigate to your desired directory: `cd ~`
3. Clone your repository: `git clone https://github.com/yourusername/your-repo.git Aura_Backend_MVP`

#### Uploading a ZIP File

1. Create a ZIP file of your project directory
2. Upload it to PythonAnywhere through Files > Upload a file
3. Extract it: 
   ```bash
   cd ~
   unzip your-zipfile.zip -d Aura_Backend_MVP
   ```

### 2. Set Up a Virtual Environment

1. Open a Bash console on PythonAnywhere
2. Create a virtual environment:
   ```bash
   cd ~/Aura_Backend_MVP
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### 3. Configure a Web App on PythonAnywhere

1. Go to the Web tab in PythonAnywhere
2. Click "Add a new web app"
3. Choose your domain name (username.pythonanywhere.com)
4. Select "Manual configuration"
5. Choose Python version (3.9 or newer recommended)
6. Enter the path to your project directory (e.g., /home/yourusername/Aura_Backend_MVP)

### 4. Configure the WSGI File

1. In the Web tab, click the link to the WSGI configuration file
2. Replace the contents with the following (adjust paths as needed):

```python
import sys
import os

# Add your project directory to path
path = '/home/yourusername/Aura_Backend_MVP'
if path not in sys.path:
    sys.path.append(path)

# Import your application
from wsgi import application
```

### 5. Set the Working Directory and Virtual Environment

In the Web tab:
1. Set "Source code" to: `/home/yourusername/Aura_Backend_MVP`
2. Set "Working directory" to: `/home/yourusername/Aura_Backend_MVP`
3. Set "Virtualenv" to: `/home/yourusername/Aura_Backend_MVP/venv`

### 6. Configure Static Files (if needed)

If your FastAPI application serves static files:
1. In the Web tab, add a static files mapping:
   - URL: `/static/`
   - Directory: `/home/yourusername/Aura_Backend_MVP/static`

### 7. Reload Your Web App

1. Click the "Reload" button in the Web tab
2. Your FastAPI application should now be live at yourusername.pythonanywhere.com

## Troubleshooting

Check the error logs in the Web tab if you encounter any issues:
- Access the error log
- Look for specific error messages
- Check the server log for more details

Common issues:
- Missing dependencies in requirements.txt
- Incorrect path configurations
- WSGI configuration issues

## Maintaining Your Deployment

To update your deployed application:
1. Pull the latest code from your repository or upload new files
2. Update dependencies if needed
3. Reload the web app

## API Documentation

Once deployed, your FastAPI documentation will be available at:
- Swagger UI: https://yourusername.pythonanywhere.com/docs
- ReDoc: https://yourusername.pythonanywhere.com/redoc
