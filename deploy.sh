#!/bin/bash
set -e

# Variables
APP_DIR="/home/appuser/syvrona-ai"
TAG=$1  # The git tag to deploy, e.g., prod-20240616-1100

if [ -z "$TAG" ]; then
    echo "Usage: $0 <git-tag>"
    exit 1
fi

echo "Deploying tag: $TAG"
cd $APP_DIR

echo "Stopping containers..."
docker compose down

echo "Fetching latest code..."
git fetch --all --tags
git checkout $TAG

echo "Building and starting containers..."
docker compose -f docker-compose.yml up -d --build

echo "Running database migrations..."
docker compose exec web flask db upgrade

echo "Deployment complete!"
