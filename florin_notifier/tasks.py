import base64
import requests
import logging
import json
import datetime
import os
import gnupg
from rogersbank.client import RogersBankClient
from rogersbank.secret_provider import DictionaryBasedSecretProvider as RogersBankSecretProvider
from tangerine import TangerineClient, DictionaryBasedSecretProvider as TangerineSecretProvider
from collections import defaultdict
from . import redis


logger = logging.getLogger(__name__)


def create_provider(filename, provider_factory):
    gpg = gnupg.GPG(gnupghome=os.path.expanduser('~/.gnupg'))
    with open(filename) as f:
        crypt = gpg.decrypt(f.read())
    secret = json.loads(crypt.data.decode('ascii'))
    return provider_factory(secret)


def get_new_transactions(previous, current):
    return [txn for txn in current if txn not in previous]


def tangerine_client_factory(secret_file):
    secret_provider = create_provider(secret_file, provider_factory=TangerineSecretProvider)
    tangerine_client = TangerineClient(secret_provider)
    return tangerine_client


class NewTransactionNotifier():
    def __init__(self, account_ids, recipient, client=None, email=None):
        self._account_ids = account_ids
        self._recipient = recipient
        self._client = client

        if not email:
            from . import email
        self._email = email

    @property
    def key_prefix(self):
        raise NotImplementedError()

    @property
    def client(self):
        return self._client

    def get_new_transactions(self, previous, current):
        return [txn for txn in current if txn not in previous]

    def group_transactions_by_account_id(self, txns):
        return txns

    def transaction_adapter(self, t):
        """Adapts the transaction so it can be rendered by the template.

        The template requires keys:
            - date
            - amount
            - description
        """
        return t

    def fetch_current_transactions(self):
        raise NotImplementedError()

    def __call__(self):
        previous_scrapes = redis.get_sorted_keys('{}*'.format(self.key_prefix))

        now = datetime.datetime.now()
        from_ = (now - datetime.timedelta(days=1)).date()

        if len(previous_scrapes) < 1:
            previous = []
        else:
            key = previous_scrapes[-1]
            try:
                key = key.decode('ascii')
                from_ = key.split(self.key_prefix)[-1]
                from_ = datetime.datetime.strptime(from_, '%Y-%m-%dT%H:%M:%S.%f')
                previous = redis.retrieve(key)
            except:
                logger.warn('Could not process key: {}.'.format(key))
                previous = []

        to_ = now.date() + datetime.timedelta(days=1)
        logger.info('Scrapping from {} to {}'.format(from_, to_))

        key = '{}{}'.format(self.key_prefix, now.isoformat())
        with self.client.login():
            current = self.fetch_current_transactions(from_, to_)
            redis.store(key, current)

        new_transactions = self.group_transactions_by_account_id(self.get_new_transactions(previous, current))
        self._email.send_new_transaction_email(self._recipient, new_transactions, self.transaction_adapter)


class TangerineTransactionNotifier(NewTransactionNotifier):
    @property
    def key_prefix(self):
        return 'scrape:tangerine:'

    def transaction_adapter(self, t):
        t = dict(t)
        t['date'] = t['posted_date']
        return t

    def group_transactions_by_account_id(self, txns):
        grouped_txns = defaultdict(list)
        for txn in txns:
            grouped_txns[txn['account_id']].append(txn)
        return grouped_txns

    def fetch_current_transactions(self, period_from, period_to):
        return self.client.list_transactions(self._account_ids, period_from=period_from, period_to=period_to)


class RogersBankTransactionNotifier(NewTransactionNotifier):
    def __init__(self, account_ids, *args, **kwargs):
        if len(account_ids) != 1:
            raise AssertionError('Currently only one account for RogersBank per login is supported')
        super().__init__(account_ids, *args, **kwargs)

    @property
    def key_prefix(self):
        return 'scrape:tangerine:'

    def fetch_current_transactions(self, period_from, period_to):
        return self.client.recent_activities

    def group_transactions_by_account_id(self, txns):
        return {self._account_ids[0]: txns}  # TODO: single account supported currently


def notify_tangerine_transactions(account_ids,
                                  secret_file,
                                  recipient,
                                  tangerine_client=None,
                                  email=None):
    if tangerine_client is None:
        secret_provider = create_provider(secret_file, provider_factory=TangerineSecretProvider)
        tangerine_client = TangerineClient(secret_provider)
    notifier = TangerineTransactionNotifier(account_ids, recipient, tangerine_client, email)
    return notifier()


def notify_rogersbank_transactions(account_ids,
                                   secret_file,
                                   recipient,
                                   rogersbank_client=None,
                                   email=None):
    if rogersbank_client is None:
        secret_provider = create_provider(secret_file, provider_factory=RogersBankSecretProvider)
        rogersbank_client = RogersBankClient(secret_provider)
    notifier = RogersBankTransactionNotifier(account_ids, recipient, rogersbank_client, email)
    return notifier()


class FireflyStatementImporter():
    pass


class RogersBankFireflyStatementImporter(FireflyStatementImporter):
    def __init__(self, secret_file):
        secret_provider = create_provider(secret_file, provider_factory=RogersBankSecretProvider)
        self._client = RogersBankClient(secret_provider)

    def __call__(self, account_ids, firefly_config):
        assert len(account_ids) == 1
        endpoint = firefly_config['endpoint']
        account_id_mapping = firefly_config['account_id_mapping']

        firefly_account_id = account_id_mapping[account_ids[0]]

        with self._client.login():
            content = self._client.download_statement('00', save=False)

        response = requests.post(endpoint, json={
            'user_id': firefly_config['user_id'],
            'account_id': firefly_account_id,
            'data': base64.b64encode(content.encode('ascii')).decode('ascii'),
        })

        response.raise_for_status()


class TangerineFireflyStatementImporter(FireflyStatementImporter):
    def __init__(self, secret_file):
        secret_provider = create_provider(secret_file, provider_factory=TangerineSecretProvider)
        self._client = TangerineClient(secret_provider)


STATEMENT_IMPORTER = {
    'rogersbank': RogersBankFireflyStatementImporter,
    'tangerine': TangerineFireflyStatementImporter,
}


def upload_statement_to_firefly(bank, account_ids, secret_file, firefly_config, client=None):
    assert bank in STATEMENT_IMPORTER
    importer = STATEMENT_IMPORTER[bank](secret_file)
    return importer(account_ids, firefly_config)
