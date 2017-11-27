import os
import sendgrid
import logging
from sendgrid.helpers.mail import Email, Content, Mail
from jinja2 import Environment, FileSystemLoader


EMAIL_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'email_template')


env = Environment(loader=FileSystemLoader(EMAIL_TEMPLATE_DIR),
                  trim_blocks=True)


logger = logging.getLogger(__name__)


def sendgrid_client(sendgrid_api_key):
    return sendgrid.SendGridAPIClient(apikey=sendgrid_api_key)


def send_email(sendgrid_client, recipient, content):
    from_email = Email('noreply@idempotent.ca')
    to_email = Email(recipient)
    subject = 'New Transactions'
    content = Content('text/html', content)
    mail = Mail(from_email, subject, to_email, content)
    response = sendgrid_client.client.mail.send.post(request_body=mail.get())
    logger.info(response.status_code)
    logger.info(response.body)
    logger.info(response.headers)


def render_template(template_name, context):
    return env.get_template(template_name).render(**context)
