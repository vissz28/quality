.PHONY: install run dev build up down logs lint fmt test clean

install:
	pip install -r requirements.txt -r requirements-dev.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

build:
	docker build -t mr-test-generator .

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	ruff check app

fmt:
	ruff format app

test:
	pytest -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
