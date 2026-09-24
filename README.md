# GroundConnect AI

GroundConnect AI is a FastAPI-based backend for AI services, authorization, security, messaging, incident response, notifications, observability, and related platform APIs.

## Requirements

- Python 3.14+
- pip

## Setup

Create and activate a virtual environment:

    python -m venv .venv
    .venv\Scripts\Activate.ps1

Install dependencies:

    python -m pip install -r requirements.txt

## Environment Configuration

Copy the example environment file:

    Copy-Item .env.example .env

Review `.env` before starting the application.

The application uses `.env` through Pydantic Settings. Encryption is enabled by default and requires a valid `ENCRYPTION_KEY`.

## Run Locally

Start the FastAPI application:

    python -m uvicorn app.main:app --reload

The API will be available at:

    http://127.0.0.1:8000

FastAPI documentation:

    http://127.0.0.1:8000/docs

## Run Tests

Run the complete test suite:

    python -m pytest -q

## Notes

- Do not commit `.env` or other files containing secrets.
- Use `.env.example` as the template for local configuration.
- Destructive recovery test-data cleanup is disabled by default.