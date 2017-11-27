import json
import logging
import datetime
import subprocess
from tangerine import TangerineClient, DictionaryBasedSecretProvider


FROM = datetime.date(2017, 6, 1)
TO = datetime.date(2017, 11, 2)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    output = subprocess.check_output(['gpg', '-d', 'secrets/tangerine.json.gpg'])
    secret_provider = DictionaryBasedSecretProvider(json.loads(output))
    client = TangerineClient(secret_provider)
    with client.login():
        accounts = [
            acct for acct in client.list_accounts()
            if acct['type'] != 'CREDIT_CARD'
        ]

        def haha(from_, to_):
            txns = client.list_transactions(['3132333435363738393031323334353621dd20f68fd39fc584681e37b04c9738'],
                                            period_from=datetime.date(2017, 11, from_),
                                            period_to=datetime.date(2017, 11, to_))
            return txns
        import pdb; pdb.set_trace()  # XXX BREAKPOINT
        print('fooo')

        # for acct in accounts:
        #     try:
        #         client.download_ofx(acct, FROM, TO)
        #     except UnsupportedAccountTypeForDownload as e:
        #         print(e)
