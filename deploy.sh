#!/bin/bash
set -eu

# Variables
APP_DIR="/home/appuser/syvrona-ai"
TAG="$1"  # The git tag to deploy, e.g., prod-20240616-1100

if [ -z "$TAG" ]; then
    echo "Usage: $0 <git-tag>"
    exit 1
fi

echo "Deploying tag: $TAG"
cd "$APP_DIR"

echo "Enabling Maintenance Mode..."
touch /srv/maintenance/enabled

# Always clean up maintenance mode on exit
trap 'rm -f /srv/maintenance/enabled' EXIT

echo "Stopping containers..."
docker compose down

echo "Fetching latest code and cleaning working directory..."
git fetch --all --tags
git reset --hard
git clean -fd
git checkout "$TAG"

echo "Building and starting containers..."
docker compose -f docker-compose.yml up -d --build

# Wait for the web container to be healthy
echo "Waiting for syvrona-ai-web-1 to be healthy..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' syvrona-ai-web-1)" = "healthy" ]; do
  sleep 2
done
echo "syvrona-ai-web-1 is healthy, proceeding with migrations..."

docker exec syvrona-ai-web-1 flask db upgrade

echo "Deployment complete!"
