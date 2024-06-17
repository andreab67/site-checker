# Use a base image with necessary tools
FROM python:3.11-slim-bookworm AS base

# Set up environment variables
ENV WEBSITE_URL="The website address you would likle to check"
ENV EMAIL_SENDER="the identity email that has permissions to send from teh solution you use ( I used AWS SES) hint DKIM"
ENV EMAIL_RECEIVER1="first email that receives notifications when the site changes"
ENV EMAIL_RECEIVER2="second email that receives notifications when the site changes"
ENV SMTP_PORT="587"
ENV SMTP_USERNAME="SMTP-Username"
ENV SMTP_PASSWORD="SMTP-Password"
ENV TZ="America/Denver"

# Set the working directory
WORKDIR /app

# Copy the necessary files into the container
COPY requirements.txt .
COPY monitor.py .

# Install htop
# RUN apt-get install htop -y

# Update system
RUN apt update && apt dist-upgrade -y && apt install tzdata -y 

# upgrade pip
RUN pip install --upgrade pip

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the monitor script
ENTRYPOINT ["python", "monitor.py"]
