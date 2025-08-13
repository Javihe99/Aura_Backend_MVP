# Git Deployment Guide for PythonAnywhere

This guide will walk you through deploying your FastAPI application on PythonAnywhere using Git.

## Prerequisites

1. A PythonAnywhere account
2. A Git repository with your project
3. Git installed on your local machine

## Local Setup

If you haven't already set up your Git repository, follow these steps:

1. Initialize Git in your project directory:
   ```bash
   git init
   ```

2. Add your files to Git:
   ```bash
   git add .
   ```

3. Commit your files:
   ```bash
   git commit -m "Initial commit for PythonAnywhere deployment"
   ```

4. Create a repository on GitHub, GitLab, or any other Git hosting service

5. Add the remote repository:
   ```bash
   git remote add origin https://github.com/yourusername/your-repo.git
   ```

6. Push your code:
   ```bash
   git push -u origin main
   # or for older Git versions:
   # git push -u origin master
   ```

## Deployment on PythonAnywhere

### 1. Clone Your Repository

1. Log in to PythonAnywhere
2. Open a Bash console (Dashboard > Consoles > Bash)
3. Clone your repository:
   ```bash
   cd ~
   git clone https://github.com/yourusername/your-repo.git Aura_Backend_MVP
   ```

### 2. Set Up Virtual Environment

1. In the same Bash console:
   ```bash
   cd ~/Aura_Backend_MVP
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### 3. Configure Web App

1. Go to the Web tab in PythonAnywhere
2. Click "Add a new web app"
3. Choose your domain name (yourusername.pythonanywhere.com)
4. Select "Manual configuration"
5. Choose Python version (3.9 or newer recommended)

### 4. Configure WSGI File

1. In the Web tab, click the link to the WSGI configuration file
2. Replace the contents with:

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

### 5. Set Environment Variables

In the Web tab:
1. Set "Source code" to: `/home/yourusername/Aura_Backend_MVP`
2. Set "Working directory" to: `/home/yourusername/Aura_Backend_MVP`
3. Set "Virtualenv" to: `/home/yourusername/Aura_Backend_MVP/venv`

### 6. Reload Web App

1. Click the "Reload" button in the Web tab
2. Your FastAPI application should now be live

## Updating Your Deployment

When you make changes to your code:

1. Push changes to your Git repository:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push
   ```

2. Pull changes on PythonAnywhere:
   ```bash
   # Open a Bash console on PythonAnywhere
   cd ~/Aura_Backend_MVP
   git pull
   ```

3. Reload your web app in the Web tab

## Using the Deployment Helper Script

For easier setup, you can run our helper script after cloning:
```bash
cd ~/Aura_Backend_MVP
bash setup_pythonanywhere.sh
```

## Verifying Your Deployment

Once deployed, verify your application is working:
```bash
cd ~/Aura_Backend_MVP
python verify_deployment.py https://yourusername.pythonanywhere.com
```
