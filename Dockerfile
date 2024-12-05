# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install specific versions of scikit-learn and joblib
RUN pip install scikit-learn==1.5.2 joblib==1.2.0 pyarrow

# Make port 5001 available to the world outside this container
EXPOSE 5001

# Define the command to run the app
CMD ["python", "app.py"]