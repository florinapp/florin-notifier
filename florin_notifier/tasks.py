import logging
import json
import datetime
import os
from rogersbank.client import RogersBankClient
from rogersbank.secret_provider import DictionaryBasedSecretProvider
import gnupg
import sendgrid
from sendgrid.helpers.mail import Email, Content, Mail
from .redis import r


logger = logging.getLogger(__name__)


DAY = 24 * 60 * 60


def create_provider(filename):
    gpg = gnupg.GPG(gnupghome=os.path.expanduser('~/.gnupg'))
    with open(filename) as f:
        crypt = gpg.decrypt(f.read())
    secret = json.loads(crypt.data.decode('ascii'))
    return DictionaryBasedSecretProvider(secret)


def get_new_transactions(previous, current):
    return [txn for txn in current if txn not in previous]


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


def notify_new_transactions(account_name, secret_file, recipient):
    secret_provider = create_provider(secret_file)
    client = RogersBankClient(secret_provider)
    previous_scrapes = sorted(r.keys('scrape:rogersbank:*'))
    current_scrape_time = datetime.datetime.utcnow().isoformat()
    key = 'scrape:rogersbank:{}'.format(current_scrape_time)
    with client.login():
        current = client.recent_activities
        r.set(key, json.dumps(current), ex=1 * DAY)
    if len(previous_scrapes) < 1:
        previous = []
    else:
        previous = json.loads(r.get(previous_scrapes[-1]))

    new_transactions = get_new_transactions(previous, current)
    if len(new_transactions):
        logger.info('{} new transactions discovered'.format(len(new_transactions)))
        email_content = '<br/>'.join([','.join((t['date'], t['description'], t['amount'])) for t in new_transactions])
        send_email(secret_provider.secret_dict['sendgrid_api_key'], recipient, email_content)
    else:
        logger.info('No new transactions')
