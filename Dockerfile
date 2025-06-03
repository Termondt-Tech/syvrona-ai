# Use the official Python image as the base image
FROM python:3.12-slim

# Create non-root user and group
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file to the working directory
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Change ownership of files to appuser
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the port on which the Flask app will run
EXPOSE 5000

# Set the command to run the Flask app
CMD ["python", "app.py"]