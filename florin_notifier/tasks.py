import dateutils
import logging
import json
import datetime
import os
from rogersbank.client import RogersBankClient
from rogersbank.secret_provider import DictionaryBasedSecretProvider as RogersBankSecretProvider
from tangerine import TangerineClient, DictionaryBasedSecretProvider as TangerineSecretProvider
import gnupg
from .email import sendgrid_client, send_email, render_template
from . import redis
from .config import config


logger = logging.getLogger(__name__)


def create_provider(filename, provider_factory):
    gpg = gnupg.GPG(gnupghome=os.path.expanduser('~/.gnupg'))
    with open(filename) as f:
        crypt = gpg.decrypt(f.read())
    secret = json.loads(crypt.data.decode('ascii'))
    return provider_factory(secret)


def get_new_transactions(previous, current):
    return [txn for txn in current if txn not in previous]


def notify_tangerine_transactions(account_ids, secret_file, recipient, tangerine_client=None, sendgrid_client=None):
    # the keys are in the format: scrape:tangerine:%Y%m%d%H%M%S
    if not tangerine_client:
        secret_provider = create_provider(secret_file, provider_factory=TangerineSecretProvider)
        client = TangerineClient(secret_provider)
    else:
        client = tangerine_client

    previous_scrapes = redis.get_sorted_keys('scrape:tangerine:*')

    now = datetime.datetime.now()
    from_ = (now - datetime.timedelta(days=1)).date()

    if len(previous_scrapes) < 1:
        previous = []
    else:
        key = previous_scrapes[-1]
        try:
            from_ = key.split('scrape:tangerine:')[-1]
            # from_ = datetime.strptime(from_, '%Y%m%d%H%M%S').date()
            from_ = dateutils.parser.parse(from_).date()
            previous = redis.retrieve(key)
        except:
            logger.warn('Could not process key: {}.'.format(key))
            previous = []

    to_ = now.date() + datetime.timedelta(days=1)
    logger.info('Scrapping from {} to {}'.format(from_, to_))

    # key = 'scrape:tangerine:{}'.format(now.strftime('%Y%m%d%H%M%S'))
    key = 'scrape:tangerine:{}'.format(now.isoformat())
    with client.login():
        current = client.list_transactions(account_ids, period_from=from_, period_to=to_)
        redis.store(key, current)

    new_transactions = get_new_transactions(previous, current)
    if len(new_transactions):
        logger.info('{} new transactions discovered'.format(len(new_transactions)))
        email_content = render_template(
            'new_transactions.html.jinja2',
            {
                'txns': new_transactions,
                'account_ids': account_ids,
            }
        )
        if sendgrid_client is None:
            sendgrid_client = sendgrid_client(config['sendgrid_api_key'])
        send_email(sendgrid_client, recipient, email_content)
    else:
        logger.info('No new transactions')


def notify_new_transactions(account_name, secret_file, recipient):
    secret_provider = create_provider(secret_file, provider_factory=RogersBankSecretProvider)
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
        send_email(
            sendgrid_client(config['sendgrid_api_key']),
            recipient, email_content)
    else:
        logger.info('No new transactions')
