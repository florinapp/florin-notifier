import logging
import json
import datetime
import os
from rogersbank.client import RogersBankClient
from rogersbank.secret_provider import DictionaryBasedSecretProvider
import gnupg
from .email import send_email, render_template
from . import redis


logger = logging.getLogger(__name__)


def create_provider(filename):
    gpg = gnupg.GPG(gnupghome=os.path.expanduser('~/.gnupg'))
    with open(filename) as f:
        crypt = gpg.decrypt(f.read())
    secret = json.loads(crypt.data.decode('ascii'))
    return DictionaryBasedSecretProvider(secret)


def get_new_transactions(previous, current):
    return [txn for txn in current if txn not in previous]


def notify_new_transactions(account_name, secret_file, recipient):
    secret_provider = create_provider(secret_file)
    client = RogersBankClient(secret_provider)
    previous_scrapes = redis.get_sorted_keys('scrape:rogersbank:*')
    current_scrape_time = datetime.datetime.utcnow().isoformat()
    key = 'scrape:rogersbank:{}'.format(current_scrape_time)
    with client.login():
        current = client.recent_activities
        redis.store(key, current)

    if len(previous_scrapes) < 1:
        previous = []
    else:
        previous = redis.retrieve(previous_scrapes[-1])

    new_transactions = get_new_transactions(previous, current)
    if len(new_transactions):
        logger.info('{} new transactions discovered'.format(len(new_transactions)))
        email_content = render_template(
            'new_transactions.html.jinja2',
            {
                'txns': new_transactions,
                'account_name': account_name,
            }
        )
        send_email(secret_provider.secret_dict['sendgrid_api_key'], recipient, email_content)
    else:
        logger.info('No new transactions')
