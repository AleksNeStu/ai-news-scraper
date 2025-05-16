#!/bin/bash

# Script to set up Azure DevOps Pipeline for AI News Scraper

# Check for Azure CLI
if ! command -v az >/dev/null 2>&1; then
    echo "Azure CLI is not installed. Please install it first."
    exit 1
fi

# Ensure logged in to Azure
echo "Checking Azure login status..."
az account show >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Please log in to Azure first using 'az login'"
    exit 1
fi

# Variables
RESOURCE_GROUP="ai-news-scraper-rg"
LOCATION="eastus"
ACR_NAME="ainewsscraperregistry"
APP_SERVICE_PLAN="ai-news-scraper-plan"
STAGING_APP_NAME="ai-news-scraper-staging"
PROD_APP_NAME="ai-news-scraper-prod"
QDRANT_NAME="ai-news-scraper-qdrant"

# Create Resource Group
echo "Creating Resource Group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# Create Azure Container Registry
echo "Creating Azure Container Registry..."
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true

# Create App Service Plan
echo "Creating App Service Plan..."
az appservice plan create --resource-group "$RESOURCE_GROUP" --name "$APP_SERVICE_PLAN" \
    --is-linux --sku B1

# Create Web Apps for Containers
echo "Creating Staging Web App..."
az webapp create --resource-group "$RESOURCE_GROUP" --plan "$APP_SERVICE_PLAN" \
    --name "$STAGING_APP_NAME" --deployment-container-image-name mcr.microsoft.com/appsvc/staticsite:latest

echo "Creating Production Web App..."
az webapp create --resource-group "$RESOURCE_GROUP" --plan "$APP_SERVICE_PLAN" \
    --name "$PROD_APP_NAME" --deployment-container-image-name mcr.microsoft.com/appsvc/staticsite:latest

# Create Container Instance for Qdrant (for Production)
echo "Creating Qdrant Container Instance..."
az container create --resource-group "$RESOURCE_GROUP" --name "$QDRANT_NAME" \
    --image qdrant/qdrant:latest --dns-name-label "$QDRANT_NAME" \
    --ports 6333 6334 --ip-address public

# Get Qdrant FQDN
QDRANT_FQDN=$(az container show --resource-group "$RESOURCE_GROUP" --name "$QDRANT_NAME" --query ipAddress.fqdn -o tsv)
QDRANT_URL="http://$QDRANT_FQDN:6333"

echo "Configuration complete!"
echo "==== Important Information ===="
echo "ACR Name: $ACR_NAME"
echo "Staging App Name: $STAGING_APP_NAME"
echo "Production App Name: $PROD_APP_NAME"
echo "Qdrant URL: $QDRANT_URL"
echo "============================"
echo "Now set up these variables in your Azure DevOps Pipeline:"
echo "ACR_NAME: $ACR_NAME"
echo "STAGING_APP_NAME: $STAGING_APP_NAME"
echo "PRODUCTION_APP_NAME: $PROD_APP_NAME"
echo "QDRANT_URL: $QDRANT_URL"

exit 0
