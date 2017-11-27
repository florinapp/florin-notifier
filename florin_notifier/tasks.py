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


class NewTransactionNotifier():
    def __init__(self, account_ids, secret_file, recipient, tangerine_client=None, sendgrid_client=None):
        self._account_ids = account_ids
        self._secret_file = secret_file
        self._recipient = recipient

        if not tangerine_client:
            secret_provider = create_provider(secret_file, provider_factory=TangerineSecretProvider)
            tangerine_client = TangerineClient(secret_provider)
        self._tangerine_client = tangerine_client

        if not sendgrid_client:
            sendgrid_client = sendgrid_client(config['sendgrid_api_key'])
        self._sendgrid_client = sendgrid_client

    @property
    def key_prefix(self):
        return 'scrape:tangerine:'

    @property
    def client(self):
        return self._tangerine_client

    def send_email(self, new_transactions):
        if not len(new_transactions):
            logger.info('No new transactions')
            return

        logger.info('{} new transactions discovered'.format(len(new_transactions)))
        email_content = render_template(
            'new_transactions.html.jinja2',
            {
                'txns': new_transactions,
                'account_ids': self._account_ids,
            }
        )
        send_email(self._sendgrid_client, self._recipient, email_content)

    def __call__(self):
        previous_scrapes = redis.get_sorted_keys('{}*'.format(self.key_prefix))

        now = datetime.datetime.now()
        from_ = (now - datetime.timedelta(days=1)).date()

        if len(previous_scrapes) < 1:
            previous = []
        else:
            key = previous_scrapes[-1]
            try:
                from_ = key.split(self.key_prefix)[-1]
                from_ = dateutils.parser.parse(from_).date()
                previous = redis.retrieve(key)
            except:
                logger.warn('Could not process key: {}.'.format(key))
                previous = []

        to_ = now.date() + datetime.timedelta(days=1)
        logger.info('Scrapping from {} to {}'.format(from_, to_))

        key = '{}{}'.format(self.key_prefix, now.isoformat())
        with self.client.login():
            current = self.client.list_transactions(self._account_ids, period_from=from_, period_to=to_)
            redis.store(key, current)

        new_transactions = get_new_transactions(previous, current)
        self.send_email(new_transactions)


def notify_tangerine_transactions(account_ids, secret_file, recipient, tangerine_client=None, sendgrid_client=None):
    notifier = NewTransactionNotifier(account_ids, secret_file, recipient, tangerine_client, sendgrid_client)
    return notifier()


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
