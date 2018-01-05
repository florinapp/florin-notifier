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
from dateutil.relativedelta import relativedelta
from .couchdb_importer import CouchDBImporter
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
        return 'scrape:rogersbank:'

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


class RogersBankStatementImporter():
    def __init__(self, secret_file):
        secret_provider = create_provider(secret_file, provider_factory=RogersBankSecretProvider)
        self._client = RogersBankClient(secret_provider)

    def upload(self, statement_content, target_account_id, target):
        raise NotImplemented()

    def __call__(self, account_ids, targets):
        assert len(account_ids) == 1
        with self._client.login():
            content = self._client.download_statement('00', save=False)

        for target in targets:
            account_id_mapping = target.get('account_id_mapping', {})
            target_account_id = account_id_mapping.get(account_ids[0])
            self.upload(content, target_account_id, target)


class RogersBankFireflyStatementImporter(RogersBankStatementImporter):
    def upload(self, statement_content, target_account_id, target):
        endpoint = target['endpoint']
        request_json = {
            'account_id': target_account_id,
            'data': base64.b64encode(statement_content.encode('ascii')).decode('ascii'),
        }

        if target.get('user_id') is not None:
            request_json.update({
                'user_id': target['user_id'],
            })

        response = requests.post(endpoint, json=request_json, timeout=300)

        if response.status_code != 200:
            logger.warn('Failed: status={};msg={}'.format(response.status_code, response.text))


class RogersBankFlorinV2StatementImporter(CouchDBImporter, RogersBankStatementImporter):
    pass


class TangerineStatementImporter():
    def __init__(self, secret_file):
        secret_provider = create_provider(secret_file, provider_factory=TangerineSecretProvider)
        self._client = TangerineClient(secret_provider)

    def _get_date_range(self):
        today = datetime.date.today()
        from_ = today - relativedelta(months=1)
        to_ = today + relativedelta(days=1)
        return from_, to_

    def upload(self, statement_content, target_account_id, target):
        raise NotImplemented()

    def __call__(self, account_ids, targets):
        from_, to_ = self._get_date_range()

        with self._client.login():
            accounts = self._client.list_accounts()
            accounts = {
                acct['number']: acct
                for acct in accounts
            }
            for account_id in account_ids:
                account_obj = accounts.get(account_id)
                if not account_obj:
                    logger.warn('Account {} does not exist. Skip...'.format(account_id))
                    continue
                for target in targets:
                    account_id_mapping = target.get('account_id_mapping', {})

                    target_account_id = account_id_mapping.get(account_id)
                    content = self._client.download_ofx(account_obj, from_, to_, save=False)
                    self.upload(content, target_account_id, target)


class TangerineFireflyStatementImporter(TangerineStatementImporter):
    def upload(self, statement_content, target_account_id, target):
        if not target_account_id:
            logger.warn('Account {} does not have a corresponding firefly id. Skip...'.format(target_account_id))
            return

        endpoint = target['endpoint']
        request_json = {
            'account_id': target_account_id,
            'data': base64.b64encode(statement_content.encode('ascii')).decode('ascii'),
        }

        if target.get('user_id') is not None:
            request_json.update({'user_id': target.get('user_id')})

        response = requests.post(endpoint, json=request_json, timeout=300)
        if response.status_code != 200:
            logger.warn('Failed: status={};msg={}'.format(response.status_code, response.text))


class TangerineFlorinV2StatementImporter(CouchDBImporter, TangerineStatementImporter):
    pass


STATEMENT_IMPORTER = {
    'rogersbank': RogersBankFireflyStatementImporter,
    'tangerine': TangerineFireflyStatementImporter,
    'rogersbank_florin': RogersBankFlorinV2StatementImporter,
    'tangerine_florin': TangerineFlorinV2StatementImporter,
}


def upload_statement(bank, account_ids, secret_file, targets, client=None):
    assert bank in STATEMENT_IMPORTER
    importer = STATEMENT_IMPORTER[bank](secret_file)
    return importer(account_ids, targets)
