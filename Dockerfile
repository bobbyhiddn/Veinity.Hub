FROM python:3.11-slim

# Install git and other dependencies
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Install gunicorn
RUN pip install gunicorn

# Expose the port
EXPOSE 8888

# Make sure we're in the src directory
WORKDIR /app/src

CMD ["gunicorn", "-w", "4
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8888", "app:app"]]