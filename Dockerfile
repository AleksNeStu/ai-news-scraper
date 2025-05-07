FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required for newspaper3k
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    curl \
    git \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install NLTK punkt package required by newspaper3k
RUN python -m pip install --no-cache-dir nltk && \
    python -c "import nltk; nltk.download('punkt')"

# Copy only requirements to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add Streamlit dependencies
RUN pip install --no-cache-dir streamlit>=1.28.0 altair>=5.0.0 pandas>=2.0.0

# Copy project files
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port for Streamlit
EXPOSE 8501

# Command to run the application
CMD ["streamlit", "run", "src/ui/app.py"]
