# AI-Powered Battery Fitness Assessment Platform

A Django application for managing athletes and fitness assessments, with pose analysis powered by Ultralytics YOLO.

## Local setup

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set a fresh `DJANGO_SECRET_KEY`. Keep `.env` private.
4. Run `python manage.py migrate` and then `python manage.py runserver`.

SQLite is used by default. To use PostgreSQL, set `DB_ENGINE=postgresql` and configure `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`.

## Pose model

Model weight files are excluded from Git by `.gitignore`. Place the required `yolo26n-pose.pt` file in the project root before using pose-analysis features. Do not commit credentials, `.env`, or local database files.

## Project documents

Project and milestone documents are kept in `docs/`.
