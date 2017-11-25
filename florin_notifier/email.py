import os
import sendgrid
from sendgrid.helpers.mail import Email, Content, Mail
from jinja2 import Environment, FileSystemLoader


EMAIL_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'email_template')


env = Environment(loader=FileSystemLoader(EMAIL_TEMPLATE_DIR),
                  trim_blocks=True)


def send_email(sendgrid_api_key, recipient, content):
    sg = sendgrid.SendGridAPIClient(apikey=sendgrid_api_key)
    from_email = Email('noreply@idempotent.ca')
    to_email = Email(recipient)
    subject = 'New Transactions'
    content = Content('text/html', content)
    mail = Mail(from_email, subject, to_email, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    print(response.status_code)
    print(response.body)
    print(response.headers)


def render_template(template_name, context):
    return env.get_template(template_name).render(**context)
