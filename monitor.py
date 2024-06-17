import requests
import hashlib
import time
import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging to file and standard error
logging.basicConfig(filename='/var/log/site-checker.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')
console_handler = logging.StreamHandler()  # Log to stderr
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
console_handler.setFormatter(formatter)
logging.getLogger().addHandler(console_handler)

def fetch_website_content(url):
    """Fetch the content of the website and return its hash."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        content_hash = hashlib.md5(response.content).hexdigest()
        logging.info(f"Content fetched successfully for URL: {url}")
        return content_hash
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def send_email(subject, body):
    """Send an email with the given subject and body using Amazon SES."""
    sender_email = os.getenv('EMAIL_SENDER')
    receiver_emails = [os.getenv('EMAIL_RECEIVER1'), os.getenv('EMAIL_RECEIVER2')]  # List of email recipients
    userid = os.getenv('SMTP_USERNAME')
    password = os.getenv('SMTP_PASSWORD')

    # Setup the MIME message
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = ", ".join(receiver_emails)  # Join the list into a string separated by commas
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))

    # Use SSL for a secure connection
    try:
        with smtplib.SMTP_SSL('email-smtp.us-east-1.amazonaws.com', 465) as server:
            server.login(userid, password)
            server.sendmail(sender_email, receiver_emails, message.as_string())  # Send to multiple recipients
            logging.info("Email sent successfully!")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def main():
    url = os.getenv('WEBSITE_URL')
    check_interval = 300  # Time between checks in seconds
    logging.info(f"Monitoring {url} for changes...")
    current_hash = fetch_website_content(url)
    
    if current_hash is None:
        logging.warning("Failed to fetch website content.")
        return

    while True:
        time.sleep(check_interval)
        new_hash = fetch_website_content(url)
        
        if new_hash is None:
            logging.warning("Failed to fetch website content.")
            continue
        
        if new_hash != current_hash:
            logging.info("Website has changed!")
            send_email("Website Change Alert", f"Change detected in {url} at {time.ctime()}")
            current_hash = new_hash
        else:
            logging.info("No changes detected.")

if __name__ == "__main__":
    main()
