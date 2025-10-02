# War Site Makefile
# Convenient commands for development and deployment

.PHONY: help install dev-install test lint format clean build deploy stop logs backup

# Default target
help:
	@echo "War Site - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  install      - Install production dependencies"
	@echo "  dev-install  - Install development dependencies"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linting"
	@echo "  format       - Format code"
	@echo "  clean        - Clean up temporary files"
	@echo ""
	@echo "Docker & Deployment:"
	@echo "  build        - Build Docker images"
	@echo "  deploy       - Deploy application"
	@echo "  stop         - Stop all services"
	@echo "  restart      - Restart services"
	@echo "  logs         - Show application logs"
	@echo "  backup       - Create database backup"
	@echo ""
	@echo "Database:"
	@echo "  migrate      - Run database migrations"
	@echo "  makemigrations - Create new migrations"
	@echo "  shell        - Open Django shell"
	@echo "  dbshell      - Open database shell"

# Development commands
install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install black flake8 isort mypy

test:
	python manage.py test --settings=war_site.settings.testing

test-coverage:
	coverage run --source='.' manage.py test --settings=war_site.settings.testing
	coverage report
	coverage html

lint:
	flake8 .
	mypy .
	isort --check-only .
	black --check .

format:
	isort .
	black .

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/

# Docker commands
build:
	docker-compose build

deploy:
	./scripts/deploy.sh deploy

stop:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-celery:
	docker-compose logs -f celery-worker celery-beat

backup:
	./scripts/deploy.sh backup

# Database commands
migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

shell:
	python manage.py shell

dbshell:
	python manage.py dbshell

# Docker database commands
docker-migrate:
	docker-compose exec web python manage.py migrate

docker-makemigrations:
	docker-compose exec web python manage.py makemigrations

docker-shell:
	docker-compose exec web python manage.py shell

docker-dbshell:
	docker-compose exec web python manage.py dbshell

# Utility commands
collectstatic:
	python manage.py collectstatic --noinput

docker-collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

createsuperuser:
	python manage.py createsuperuser

docker-createsuperuser:
	docker-compose exec web python manage.py createsuperuser

# Development server
runserver:
	python manage.py runserver 0.0.0.0:8000

# Celery commands (for development)
celery-worker:
	celery -A war_site worker --loglevel=info

celery-beat:
	celery -A war_site beat --loglevel=info

celery-flower:
	celery -A war_site flower

# Security checks
check:
	python manage.py check --deploy

# Update dependencies
update-deps:
	pip list --outdated
	@echo "Run 'pip install --upgrade <package>' to update specific packages"

# Generate secret key
generate-secret:
	python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"