#!/bin/bash
# PythonAnywhere deployment setup script
# Run this script on PythonAnywhere console to set up your environment

# Set project directory
PROJECT_DIR="$HOME/Aura_Backend_MVP"
VENV_DIR="$PROJECT_DIR/venv"

echo "Setting up Aura Backend MVP in $PROJECT_DIR"

# Create and activate virtual environment
echo "Creating virtual environment..."
python -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "Installing dependencies..."
pip install -r "$PROJECT_DIR/requirements.txt"

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure your web app in the PythonAnywhere Web tab"
echo "2. Set the working directory to: $PROJECT_DIR"
echo "3. Set the virtualenv to: $VENV_DIR"
echo "4. Update the WSGI configuration file"
echo "5. Reload your web app"
echo ""
echo "See deployment_guide.md for detailed instructions."
