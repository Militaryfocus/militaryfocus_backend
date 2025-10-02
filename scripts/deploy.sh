#!/bin/bash

# War Site Deployment Script
# This script handles deployment of the War Site application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_warn ".env file not found. Creating from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warn "Please edit .env file with your configuration before continuing."
            exit 1
        else
            log_error ".env.example file not found. Please create .env file manually."
            exit 1
        fi
    fi
    
    log_info "Requirements check passed."
}

generate_secret_key() {
    python3 -c "
import secrets
import string
alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
secret_key = ''.join(secrets.choice(alphabet) for i in range(50))
print(secret_key)
"
}

setup_environment() {
    log_info "Setting up environment..."
    
    # Check if SECRET_KEY is set in .env
    if ! grep -q "^SECRET_KEY=" .env || grep -q "^SECRET_KEY=your-secret-key-here" .env; then
        log_warn "Generating new SECRET_KEY..."
        SECRET_KEY=$(generate_secret_key)
        sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
        log_info "SECRET_KEY generated and updated in .env file."
    fi
    
    # Create necessary directories
    mkdir -p logs nginx/ssl monitoring
    
    log_info "Environment setup completed."
}

build_and_start() {
    log_info "Building and starting services..."
    
    # Pull latest images
    docker-compose pull
    
    # Build application image
    docker-compose build --no-cache web
    
    # Start services
    docker-compose up -d
    
    log_info "Services started successfully."
}

run_migrations() {
    log_info "Running database migrations..."
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Run migrations
    docker-compose exec web python manage.py migrate
    
    log_info "Migrations completed."
}

create_superuser() {
    log_info "Creating superuser..."
    
    # Check if superuser already exists
    if docker-compose exec web python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
print('exists' if User.objects.filter(is_superuser=True).exists() else 'not_exists')
" | grep -q "exists"; then
        log_info "Superuser already exists."
    else
        log_warn "No superuser found. Please create one:"
        docker-compose exec web python manage.py createsuperuser
    fi
}

setup_initial_data() {
    log_info "Setting up initial data..."
    
    # Create initial content sources
    docker-compose exec web python manage.py shell -c "
from scrape_content_application.models import ContentSource

# Create Vesti source if it doesn't exist
vesti_source, created = ContentSource.objects.get_or_create(
    name='Вести',
    defaults={
        'description': 'Российский новостной портал',
        'source_link': 'https://www.vesti.ru/theme/11921',
        'period': 60,
        'youtube_link': False,
        'is_active': True
    }
)

if created:
    print('Created Vesti source')
else:
    print('Vesti source already exists')

# Create YouTube source if it doesn't exist
youtube_source, created = ContentSource.objects.get_or_create(
    name='Канал \"Военные сводки\"',
    defaults={
        'description': 'YouTube канал с военными сводками',
        'source_link': 'https://yewtu.be/channel/UCTXpFhlF-SPNMiyATwVq95Q/shorts',
        'period': 180,
        'youtube_link': True,
        'is_active': True
    }
)

if created:
    print('Created YouTube source')
else:
    print('YouTube source already exists')
"
    
    log_info "Initial data setup completed."
}

check_health() {
    log_info "Checking application health..."
    
    # Wait for application to start
    sleep 30
    
    # Check health endpoint
    if curl -f http://localhost/health/ > /dev/null 2>&1; then
        log_info "Application is healthy!"
    else
        log_error "Application health check failed. Please check logs:"
        log_error "docker-compose logs web"
        exit 1
    fi
}

show_status() {
    log_info "Deployment completed successfully!"
    echo
    echo "Services status:"
    docker-compose ps
    echo
    echo "Available endpoints:"
    echo "  - Health check: http://localhost/health/"
    echo "  - API info: http://localhost/api/"
    echo "  - Admin panel: http://localhost/admin/"
    echo "  - Legacy feed: http://localhost/api/feed/"
    echo "  - Articles API: http://localhost/api/v1/articles/"
    echo
    echo "To view logs: docker-compose logs -f"
    echo "To stop services: docker-compose down"
}

# Main deployment flow
main() {
    log_info "Starting War Site deployment..."
    
    check_requirements
    setup_environment
    build_and_start
    run_migrations
    create_superuser
    setup_initial_data
    check_health
    show_status
    
    log_info "Deployment completed!"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "update")
        log_info "Updating application..."
        docker-compose pull
        docker-compose build --no-cache web
        docker-compose up -d
        docker-compose exec web python manage.py migrate
        docker-compose exec web python manage.py collectstatic --noinput
        log_info "Update completed!"
        ;;
    "restart")
        log_info "Restarting services..."
        docker-compose restart
        log_info "Services restarted!"
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "stop")
        log_info "Stopping services..."
        docker-compose down
        log_info "Services stopped!"
        ;;
    "backup")
        log_info "Creating backup..."
        mkdir -p backups
        docker-compose exec db pg_dump -U war_site_user war_site_db > "backups/backup_$(date +%Y%m%d_%H%M%S).sql"
        log_info "Backup created in backups/ directory"
        ;;
    *)
        echo "Usage: $0 {deploy|update|restart|logs|stop|backup}"
        echo
        echo "Commands:"
        echo "  deploy  - Full deployment (default)"
        echo "  update  - Update application and restart"
        echo "  restart - Restart all services"
        echo "  logs    - Show application logs"
        echo "  stop    - Stop all services"
        echo "  backup  - Create database backup"
        exit 1
        ;;
esac