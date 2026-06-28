# CI/CD Implementation for AI News Scraper

This document outlines the CI/CD implementation for the AI News Scraper project using both GitLab CI/CD and Azure DevOps. The proposal includes configuration files, setup instructions, and best practices to ensure efficient development, testing, and deployment pipelines.

## Table of Contents

- [Overview](#overview)
- [GitLab CI/CD Implementation](#gitlab-cicd-implementation)
- [Azure DevOps Implementation](#azure-devops-implementation)
- [Environment Configuration](#environment-configuration)
- [Setup Instructions](#setup-instructions)
- [Best Practices](#best-practices)
- [Implementation Checklist](#implementation-checklist)
- [Deployment Flow Diagram](#deployment-flow-diagram)
- [Azure Solutions Used](#azure-solutions-used)
- [Additional Resources](#additional-resources)

## Overview

The AI News Scraper application requires a robust CI/CD pipeline to automate:

1. Code quality checks and linting
2. Unit and integration testing
3. Building Docker containers
4. Deployment to staging and production environments
5. Management of environment-specific configurations

The pipeline supports both GitLab and Azure DevOps platforms.

### Pipeline Workflow

```
┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│           │     │           │     │           │     │           │     │           │
│   Code    │────▶│   Lint    │────▶│   Test    │────▶│   Build   │────▶│  Deploy   │
│  Commit   │     │           │     │           │     │           │     │           │
└───────────┘     └───────────┘     └───────────┘     └───────────┘     └───────────┘
```

### Key Pipeline Features

- **Python Dependency Management**: Using Poetry
- **Code Quality**: Flake8, MyPy, Black, pytest
- **Test Coverage**: Coverage reports with minimum thresholds
- **Docker Integration**: Build and push to registry
- **Environment Management**: Development, Staging, Production
- **Security**: Secret management and authentication

## GitLab CI/CD Implementation

Create a `.gitlab-ci.yml` file in the repository root with the following configuration:

```yaml
stages:
  - lint
  - test
  - build
  - deploy

variables:
  PYTHON_VERSION: "3.12"
  DOCKER_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG
  DOCKER_IMAGE_LATEST: $CI_REGISTRY_IMAGE:latest

# Cache dependencies between jobs
cache:
  key: ${CI_COMMIT_REF_SLUG}
  paths:
    - .venv/
    - .cache/pip
    - .cache/pypoetry

# Install dependencies
.install_deps: &install_deps
  before_script:
    - python -V
    - pip install poetry
    - poetry config virtualenvs.in-project true
    - poetry install

# Lint job
lint:
  stage: lint
  image: python:${PYTHON_VERSION}-slim
  <<: *install_deps
  script:
    - poetry run flake8 src tests
    - poetry run mypy src
    - poetry run black --check src tests

# Test job
test:
  stage: test
  image: python:${PYTHON_VERSION}-slim
  <<: *install_deps
  variables:
    OFFLINE_MODE: "true"  # Run tests in offline mode
  script:
    - poetry run pytest tests/ --cov=src --cov-report=xml
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

# Build Docker image
build:
  stage: build
  image: docker:20.10.16
  services:
    - docker:20.10.16-dind
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $DOCKER_IMAGE .
    - docker push $DOCKER_IMAGE
    - |
      if [ "$CI_COMMIT_BRANCH" = "main" ]; then
        docker tag $DOCKER_IMAGE $DOCKER_IMAGE_LATEST
        docker push $DOCKER_IMAGE_LATEST
      fi
  rules:
    - if: $CI_COMMIT_BRANCH == "main" || $CI_COMMIT_TAG

# Deploy to staging
deploy_staging:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache curl
  script:
    - echo "Deploying to staging environment"
    - curl -X POST ${STAGING_WEBHOOK_URL} -H "Content-Type: application/json" -d "{\"image\": \"${DOCKER_IMAGE}\"}"
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# Deploy to production
deploy_production:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache curl
  script:
    - echo "Deploying to production environment"
    - curl -X POST ${PRODUCTION_WEBHOOK_URL} -H "Content-Type: application/json" -d "{\"image\": \"${DOCKER_IMAGE}\"}"
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_TAG
  when: manual
```

### GitLab CI/CD Pipeline Stages

1. **Lint**: Checks code quality using flake8, mypy, and black
2. **Test**: Runs pytest with coverage reporting
3. **Build**: Creates and pushes a Docker image to GitLab Container Registry
4. **Deploy**: Handles deployments to staging and production environments

#### Pipeline Visualization

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   LINT      │     │    TEST     │     │    BUILD    │     │     DEPLOY      │
├─────────────┤     ├─────────────┤     ├─────────────┤     ├─────────────────┤
│ flake8      │     │ pytest      │     │ docker      │     │ deploy_staging  │
│ mypy        │────▶│ coverage    │────▶│ build       │────▶│                 │
│ black       │     │             │     │ push        │     │ deploy_prod     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────────┘
```

## Azure DevOps Implementation

Create an `azure-pipelines.yml` file in the repository root with the following configuration:

```yaml
trigger:
  branches:
    include:
      - main
  tags:
    include:
      - v*

pool:
  vmImage: 'ubuntu-latest'

variables:
  pythonVersion: '3.12'
  DOCKER_REGISTRY: '$(ACR_NAME).azurecr.io'
  DOCKER_REPOSITORY: 'ai-news-scraper'
  DOCKER_IMAGE_NAME: '$(DOCKER_REGISTRY)/$(DOCKER_REPOSITORY)'
  DOCKER_TAG: '$(Build.BuildNumber)'

stages:
- stage: Validate
  jobs:
  - job: LintAndTest
    steps:
    - task: UsePythonVersion@0
      inputs:
        versionSpec: '$(pythonVersion)'
        addToPath: true
        
    - script: |
        python -m pip install --upgrade pip
        pip install poetry
        poetry config virtualenvs.in-project true
        poetry install
      displayName: 'Install dependencies'
      
    - script: |
        poetry run flake8 src tests
        poetry run mypy src
        poetry run black --check src tests
      displayName: 'Lint code'
      
    - script: |
        poetry run pytest tests/ --cov=src --cov-report=xml --cov-report=html
      displayName: 'Run tests'
      env:
        OFFLINE_MODE: 'true'
        
    - task: PublishCodeCoverageResults@1
      inputs:
        codeCoverageTool: Cobertura
        summaryFileLocation: '$(System.DefaultWorkingDirectory)/coverage.xml'
        reportDirectory: '$(System.DefaultWorkingDirectory)/htmlcov'
      displayName: 'Publish code coverage'

- stage: Build
  dependsOn: Validate
  condition: succeeded()
  jobs:
  - job: BuildDockerImage
    steps:
    - task: Docker@2
      inputs:
        containerRegistry: 'AzureContainerRegistry'
        repository: '$(DOCKER_REPOSITORY)'
        command: 'buildAndPush'
        Dockerfile: '**/Dockerfile'
        tags: |
          $(DOCKER_TAG)
          $(Build.SourceBranchName)
          ${{ if startsWith(variables['Build.SourceBranch'], 'refs/tags/') }}:
            latest
          ${{ endif }}
      displayName: 'Build and push Docker image'

- stage: DeployToStaging
  dependsOn: Build
  condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
  jobs:
  - deployment: DeployStaging
    environment: 'staging'
    strategy:
      runOnce:
        deploy:
          steps:
          - task: AzureWebAppContainer@1
            inputs:
              azureSubscription: 'Azure Subscription'
              appName: '$(STAGING_APP_NAME)'
              containers: '$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)'
              appSettings: |
                -OFFLINE_MODE false
                -VECTOR_DB_TYPE FAISS
                -FAISS_INDEX_PATH /app/data/vector_index
            displayName: 'Deploy to Azure Web App for Containers (Staging)'

- stage: DeployToProduction
  dependsOn: DeployToStaging
  condition: and(succeeded(), startsWith(variables['Build.SourceBranch'], 'refs/tags/'))
  jobs:
  - deployment: DeployProduction
    environment: 'production'
    strategy:
      runOnce:
        deploy:
          steps:
          - task: AzureWebAppContainer@1
            inputs:
              azureSubscription: 'Azure Subscription'
              appName: '$(PRODUCTION_APP_NAME)'
              containers: '$(DOCKER_IMAGE_NAME):$(DOCKER_TAG)'
              appSettings: |
                -OFFLINE_MODE false
                -VECTOR_DB_TYPE QDRANT
                -QDRANT_URL $(QDRANT_URL)
                -QDRANT_COLLECTION_NAME news_articles
                -OPENAI_API_KEY $(OPENAI_API_KEY)
            displayName: 'Deploy to Azure Web App for Containers (Production)'
```

### Azure DevOps Pipeline Stages

1. **Validate**: Includes both linting and testing
2. **Build**: Creates and pushes a Docker image to Azure Container Registry
3. **DeployToStaging**: Deploys to staging environment on commits to main branch
4. **DeployToProduction**: Deploys to production environment on tagged releases

#### Azure DevOps Pipeline Visualization

```
┌────────────────────┐           ┌────────────────────┐            ┌────────────────────┐
│      Validate      │           │       Build        │            │  DeployToStaging   │
│ ┌────────────────┐ │           │ ┌────────────────┐ │            │ ┌────────────────┐ │
│ │  LintAndTest   │ │───────────▶ │BuildDockerImage│ │───(main)──▶│ │DeployStaging   │ │
│ └────────────────┘ │           │ └────────────────┘ │            │ └────────────────┘ │
└────────────────────┘           └────────────────────┘            └──────────┬─────────┘
                                                                              │
                                                                              │
                                                                              ▼
                                                                   ┌────────────────────┐
                                                                   │ DeployToProduction │
                                                                   │ ┌────────────────┐ │
                                                                   │ │DeployProduction│ │
                                                                   │ └────────────────┘ │
                                                                   └────────────────────┘
                                                                      (tagged releases)
```

## Environment Configuration

The CI/CD pipelines use the following environment-specific configurations:

### Staging Environment
- Uses FAISS vector database (file-based)
- Configured with basic resources for testing
- Automatically deployed on pushes to main branch
- Environment variables:
  ```
  OFFLINE_MODE=false
  VECTOR_DB_TYPE=FAISS
  FAISS_INDEX_PATH=/app/data/vector_index
  LOG_LEVEL=INFO
  MAX_ARTICLES=100
  ```

### Production Environment
- Uses Qdrant vector database (via managed Azure Container Instance)
- Configured with production-grade resources
- Deployed only on tagged releases
- Requires manual approval for deployment
- Environment variables:
  ```
  OFFLINE_MODE=false
  VECTOR_DB_TYPE=QDRANT
  QDRANT_URL=<dynamically-generated-url>
  QDRANT_COLLECTION_NAME=news_articles
  OPENAI_API_KEY=<secured-api-key>
  LOG_LEVEL=WARNING
  MAX_ARTICLES=500
  ENABLE_CACHING=true
  ```

### Environment Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  GitLab/GitHub  │────▶│  CI/CD Pipeline │────▶│ Azure Container │
│  Repository     │     │                 │     │ Registry (ACR)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Azure Monitor  │◀────│  Azure App      │◀────│                 │
│  Application    │     │  Service        │     │  Web App        │
│  Insights       │     │  (Linux)        │     │  Container      │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐     
                        │ Azure Container │     
                        │ Instance (ACI)  │     
                        │ Qdrant Vector DB│     
                        └─────────────────┘     
```

## Setup Instructions

### GitLab CI/CD Setup

1. Add the `.gitlab-ci.yml` file to your repository.

2. Configure the following CI/CD variables in GitLab:
   - `STAGING_WEBHOOK_URL`: Webhook URL for your staging environment
   - `PRODUCTION_WEBHOOK_URL`: Webhook URL for your production environment
   - `OPENAI_API_KEY`: Your OpenAI API key (marked as masked)

3. For Docker registry authentication, GitLab automatically provides:
   - `CI_REGISTRY`: URL of the GitLab Container Registry
   - `CI_REGISTRY_USER`: Username for the registry
   - `CI_REGISTRY_PASSWORD`: Password for the registry

#### GitLab CI/CD Variables Configuration

Navigate to your GitLab project → Settings → CI/CD → Variables

| Variable | Value | Protection | Masking |
|----------|-------|------------|---------|
| STAGING_WEBHOOK_URL | https://your-staging-webhook-url | No | No |
| PRODUCTION_WEBHOOK_URL | https://your-production-webhook-url | No | No |
| OPENAI_API_KEY | your-openai-api-key | Yes | Yes |

### Azure DevOps Setup

1. Add the `azure-pipelines.yml` file to your repository root.

2. Use the setup script below to create the Azure resources:

```bash
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
```

3. In Azure DevOps, create a new pipeline and select your repository.

4. Configure the following pipeline variables:
   - `ACR_NAME`: Name of your Azure Container Registry
   - `STAGING_APP_NAME`: Name of your staging web app
   - `PRODUCTION_APP_NAME`: Name of your production web app
   - `QDRANT_URL`: URL for your Qdrant service
   - `OPENAI_API_KEY`: Your OpenAI API key (marked as secret)

#### Azure DevOps Pipeline Variables Configuration

Navigate to your Azure DevOps pipeline → Edit → Variables

| Variable | Value | Secret |
|----------|-------|--------|
| ACR_NAME | ainewsscraperregistry | No |
| STAGING_APP_NAME | ai-news-scraper-staging | No |
| PRODUCTION_APP_NAME | ai-news-scraper-prod | No |
| QDRANT_URL | http://your-qdrant-url:6333 | No |
| OPENAI_API_KEY | your-openai-api-key | Yes |

5. Create service connections in Azure DevOps:
   - Docker Registry connection to your Azure Container Registry
   - Azure Resource Manager connection to your Azure subscription

#### Service Connections Setup

**Docker Registry Connection:**
1. Go to Project Settings → Service connections → New service connection → Docker Registry
2. Select "Azure Container Registry"
3. Name it "AzureContainerRegistry"
4. Select your subscription and ACR from the dropdown

**Azure Resource Manager Connection:**
1. Go to Project Settings → Service connections → New service connection → Azure Resource Manager
2. Select "Service principal (automatic)"
3. Name it "Azure Subscription" 
4. Select the appropriate scope level and subscription

## Best Practices

1. **Environment Separation**
   - Clear separation between development, staging, and production environments
   - Environment-specific configurations stored in pipeline variables
   - Progressive promotion of code from development → staging → production

2. **Security**
   - No hardcoded secrets in configuration files
   - API keys and credentials stored as protected pipeline variables
   - Use of service connections with least privilege principle
   - Regular rotation of secrets and access keys
   - Scan Docker images for vulnerabilities before deployment

3. **Quality Control**
   - Automated code linting and testing for every commit
   - Code coverage reporting to track test effectiveness
   - Type checking with mypy for better code quality
   - Fail the pipeline if quality gates aren't met (e.g., <80% test coverage)
   - Enforce code reviews before merging to main branch

4. **Deployment Strategy**
   - Automatic deployment to staging for continuous validation
   - Manual approval required for production deployments
   - Tagged releases for production versions
   - Docker image tagging with branch name and version
   - Blue/Green deployment capability for zero-downtime updates

5. **Monitoring and Observability**
   - Application logging configuration
   - Integration with Azure Application Insights (optional)
   - Environment tagging for resource tracking
   - Alerts for deployment status (success/failure)
   - Monitoring of application health post-deployment

6. **Infrastructure as Code**
   - Azure resources created and configured via script
   - Consistent environment setup for reproducibility
   - Version-controlled infrastructure definitions
   - Parameterized environments for flexibility
   - Resource tagging for cost allocation and management

## Implementation Checklist

- [ ] Add `.gitlab-ci.yml` to repository
- [ ] Add `azure-pipelines.yml` to repository
- [ ] Create Azure resources using setup script
- [ ] Configure GitLab CI/CD variables
- [ ] Set up Azure DevOps pipeline and variables
- [ ] Create required service connections
- [ ] Test the pipeline with a pull request
- [ ] Deploy to staging environment
- [ ] Create a tagged release for production

## Deployment Flow Diagram

```
┌─────────────────┐                  ┌─────────────────┐                  ┌─────────────────┐
│                 │                  │                 │                  │                 │
│  Development    │  Pull Request    │     Staging     │   Tagged         │   Production    │
│  Branch         │─────────────────▶│     (main)      │─────────────────▶│   Environment   │
│                 │  Automated Tests │                 │   Manual Approval│                 │
└─────────────────┘                  └─────────────────┘                  └─────────────────┘
```

## Azure Solutions Used

This CI/CD implementation leverages several Azure services, each selected to address specific requirements of the AI News Scraper application. This section provides detailed information about each Azure service, its purpose in our implementation, and its pros and cons.

### Azure Container Registry (ACR)

**Purpose**: Stores and manages Docker container images for our application deployment.

**Configuration**:
- SKU: Basic (suitable for smaller teams and projects)
- Admin access: Enabled for simplified authentication
- Integrated with Azure DevOps for seamless CI/CD

**Pros**:
- Tight integration with other Azure services
- Network-close deployment to reduce latency
- Built-in vulnerability scanning for container images
- Geo-replication capabilities for enterprise scenarios
- Private network access through Azure Private Link

**Cons**:
- Cost increases with storage and bandwidth usage
- Basic tier has lower included storage (10 GB)
- Admin credentials should be rotated regularly for security
- Requires additional IAM setup for proper security in production

### Azure App Service (Web App for Containers)

**Purpose**: Hosts the containerized AI News Scraper application with minimal infrastructure management.

**Configuration**:
- Linux-based App Service Plan (B1 - Basic tier)
- Web App for Containers deployment method
- Separate instances for staging and production

**Pros**:
- Fully managed platform with automatic OS patching
- Built-in auto-scaling capabilities
- Simple deployment from container registries
- Integrated logging and monitoring
- Supports SSL/TLS termination and custom domains
- No VM management overhead

**Cons**:
- Less flexibility compared to AKS or VM-based deployments
- Cold start issues can occur with infrequently accessed apps
- B1 tier has limitations on scale and performance
- Limited control over underlying infrastructure
- File system changes are not persistent across restarts

### Azure Container Instances (ACI)

**Purpose**: Hosts the Qdrant vector database for production environment.

**Configuration**:
- Public IP address with DNS label
- Exposed ports: 6333 (API) and 6334 (monitoring)
- No persistent storage in current setup (data persistence would need to be added)

**Pros**:
- Fast startup and simple deployment
- Per-second billing (cost-effective for intermittent workloads)
- No cluster management overhead
- Easy integration with other Azure services
- Good for stateless workloads and microservices

**Cons**:
- Less suitable for high-performance persistent workloads
- Limited networking capabilities compared to AKS
- No auto-scaling capabilities
- Current implementation lacks persistent storage (would require Azure Files or similar)
- Higher cost for continuous long-running containers compared to AKS

### Azure Resource Groups

**Purpose**: Logical container for related resources, enabling unified management and access control.

**Pros**:
- Organizes resources for easier management
- Simplifies access control and permissions
- Allows bulk operations (delete, move, etc.)
- Facilitates cost tracking and billing

**Cons**:
- Resources can only belong to one resource group
- Moving resources between groups can be complex
- Some Azure resources cannot be moved between resource groups

### Alternative Azure Solutions Considered

#### Azure Kubernetes Service (AKS)

**Why Not Selected**: While AKS offers more advanced orchestration capabilities, it introduces complexity and higher management overhead not justified for this application's scale.

**Pros if Implemented**:
- Better scaling and orchestration for complex microservices
- More sophisticated deployment strategies (blue/green, canary)
- Better resource utilization for larger deployments
- Advanced networking capabilities

**Cons if Implemented**:
- Significantly higher complexity
- Requires Kubernetes expertise
- Higher operational costs
- Oversized for current application needs

#### Azure SQL Database vs. Qdrant on ACI

**Why Qdrant on ACI Was Selected**: The AI News Scraper specifically requires vector database capabilities for semantic search, which traditional SQL databases don't provide.

**Trade-offs**:
- **Data Persistence**: Current Qdrant implementation on ACI lacks persistence; in production, this should be added
- **Managed Service**: An ideal production implementation might use a fully managed vector database service
- **Scaling Considerations**: For larger datasets, a more robust Qdrant deployment on AKS might be warranted

### Cost Optimization

The selected Azure services provide a balance between cost, performance, and management overhead:

| Service | Tier | Estimated Monthly Cost | Notes |
|---------|------|------------------------|-------|
| App Service Plan | B1 | $50-$70 | Shared across staging and production |
| Container Registry | Basic | $5 | Plus storage costs (~$0.10/GB) |
| Container Instances | Pay-per-use | $20-$40 | Depends on uptime requirements |
| Total Estimated | | $75-$115 | Excluding bandwidth costs |

For cost optimization in production:
- Implement auto-scaling in App Service based on usage patterns
- Consider reserved instances for predictable workloads
- Implement image lifecycle management in ACR to reduce storage costs
- Monitor and rightsize resources based on actual usage patterns

### Security Considerations

The current implementation includes basic security measures, but production deployments should consider:

1. **Private Endpoints**: Implement Azure Private Link for ACR and other services
2. **Managed Identities**: Replace service principals with Azure Managed Identities
3. **Network Security Groups**: Restrict access to container instances
4. **Key Vault Integration**: Store all secrets in Azure Key Vault instead of pipeline variables
5. **Security Center**: Enable Azure Security Center for continuous security monitoring
