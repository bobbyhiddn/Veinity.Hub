#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print status messages
print_status() {
    echo -e "${YELLOW}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

# Function to check health endpoint
check_health() {
    local url="$1"
    local max_attempts=10
    local wait_time=10
    local attempt=1

    print_status "Checking deployment health..."
    
    while [ $attempt -le $max_attempts ]; do
        print_status "Attempt $attempt of $max_attempts"
        
        if curl -s "${url}/health" | grep -q "operational"; then
            print_success "Veinity is operational!"
            return 0
        else
            print_status "Veinity is still starting up, waiting ${wait_time} seconds..."
            sleep $wait_time
            attempt=$((attempt + 1))
        fi
    done

    print_error "Veinity failed to respond after $max_attempts attempts"
    return 1
}

# Load environment variables
if [ -f .env ]; then
    print_status "Loading environment variables..."
    export $(grep -v '^#' .env | xargs)
    print_success "Environment variables loaded"
else
    print_error ".env file not found!"
fi

# Update git repository and submodules
print_status "Updating repository and submodules..."
git pull --recurse-submodules
git submodule update --init --recursive
print_success "Repository updated"

# Set secrets on Fly.io
print_status "Setting secrets on Fly.io..."
flyctl secrets set \
    FLASK_SECRET_KEY="$FLASK_SECRET_KEY" \
    NEWSAPI_KEY="$NEWSAPI_KEY" \
    ANALYTICS_ID="$ANALYTICS_ID" \
    WEBHOOK_SECRET="$WEBHOOK_SECRET"

print_success "Secrets set successfully on Fly.io"

# Deploy to Fly.io
print_status "Deploying Veinity to Fly.io..."
if flyctl deploy; then
    print_success "Veinity has been deployed!"
    
    # Get the app URL
    APP_URL="veinity.fly.dev"
    print_status "Your application is available at: https://$APP_URL"
    
    # Check health with retries
    check_health "https://$APP_URL"
else
    print_error "Deployment failed"
fi

# Show recent logs
print_status "Recent logs from Veinity:"
flyctl logs