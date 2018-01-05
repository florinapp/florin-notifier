import logging
import couchdb
import hashlib
import ofxparse
import io


logger = logging.getLogger(__name__)


class Account():
    SIGNATURE_FIELDS = ['account_id', 'branch_id', 'currency', 'financial_institution', 'number',
                        'routing_number', 'type']

    def __init__(self, ofx_account):
        self._raw = ofx_account
        self.currency = self._raw.curdef
        self.account_id = self._raw.account_id
        self.account_type = self._raw.accoun_type
        self.branch_id = self._raw.branch_id
        self.financial_institution = self._raw.institution.organization if self._raw.institution else None
        self.number = self._raw.number
        self.routing_number = self._raw.routing_number
        self.type = self._raw.type
        self.name = self._raw.number

    @property
    def _id(self):
        signature = ''.join([str(getattr(self, field)) or '' for field in self.SIGNATURE_FIELDS])
        print(signature)
        return hashlib.sha1(signature.encode('ascii')).hexdigest()

    @property
    def json(self):
        return {
            'metadata': {
                'type': 'Account'
            },
            '_id': self._id,
            'currency': self.currency,
            'financialInstitution': self.financial_institution,
            'name': self.name,
            'history': [],
        }


class Transaction():
    SIGNATURE_FIELDS = ['amount', 'date', 'memo', 'payee', 'type', 'id']
    TYPES = {'credit': 'CREDIT', 'debit': 'DEBIT'}

    def __init__(self, ofx_txn):
        self._raw = ofx_txn
        self.amount = str(ofx_txn.amount)
        self.date = ofx_txn.date.isoformat()
        self.memo = ofx_txn.memo
        self.payee = ofx_txn.payee
        self.type = self.TYPES.get(ofx_txn.type, ofx_txn.type.upper())

    @property
    def _id(self):
        signature = ''.join([str(getattr(self._raw, field)) or '' for field in self.SIGNATURE_FIELDS])
        return hashlib.sha1(signature.encode('ascii')).hexdigest()

    @property
    def checksum(self):
        signature = ''.join([str(getattr(self._raw, field)) or '' for field in self.SIGNATURE_FIELDS])
        return 'sha256:' + hashlib.sha256(signature.encode('ascii')).hexdigest()

    @property
    def json(self):
        return {
            'metadata': {
                'type': 'Transaction'
            },
            '_id': self._id,
            'amount': self.amount,
            'date': self.date,
            'name': self.payee,
            'memo': self.memo,
            'checksum': self.checksum,
            'type': self.type
        }


class CouchDBImporter():
    def get_db(self, target):
        server = couchdb.Server(target['db_server'])
        try:
            db = server[target['db_name']]
        except:
            db = server.create(target['db_name'])
        return db

    def get_db_account(self, db, ofx_account):
        account = Account(ofx_account)
        try:
            db_account = db[account._id]
        except Exception as e:
            print(e)
            account_id = db.create(account.json)
            db_account = db[account_id]
        return db_account

    def upload(self, statement_content, target_account_id, target):
        parser = ofxparse.OfxParser()
        ofx = parser.parse(io.StringIO(statement_content))
        db = self.get_db(target)
        for ofx_account in ofx.accounts:
            db_account = self.get_db_account(db, ofx_account)
            statement = ofx_account.statement
            db_account['history'] = db_account.get('history', [])
            db_account['history'].append({
                'dateTime': statement.balance_date.isoformat(),
                'balance': str(statement.balance),
            })
            db.save(db_account)
            for ofx_txn in ofx_account.statement.transactions:
                txn = Transaction(ofx_txn)
                txn_doc = txn.json
                txn_doc['accountId'] = db_account.id
                if db.get(txn_doc['_id']):
                    logger.warn('Transaction {} already exists. Skipping'.format(txn_doc))
                    continue
                db.save(txn_doc)
                logger.info('Transaction {} imported'.format(txn_doc))
