# Aura Backend MVP

A simple FastAPI-based backend API for the Aura application.

## Features

- RESTful API endpoints
- CORS middleware for frontend integration
- Health check endpoint
- Sample items endpoint

## Local Development

### Prerequisites

- Python 3.9+
- pip

### Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```
   python run.py
   ```
   or
   ```
   uvicorn app:app --reload
   ```

## Testing

Run the tests with pytest:
```
pytest
```

## API Documentation

When running locally, access the API documentation at:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

## Deployment

See [deployment_guide.md](deployment_guide.md) for instructions on deploying to PythonAnywhere.

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /items` - Returns a list of sample items
