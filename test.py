from florin_notifier.tasks import upload_statement

# upload_statement_to_firefly(bank='rogersbank',
#                             account_ids=['XXXX1670'],
#                             secret_file='secrets/rogersbank.json.gpg',
#                             firefly_config={
#                                 "endpoint": "http://192.168.200.46:6060/import",
#                                 "user_id": "1",
#                                 "account_id_mapping": {
#                                     "XXXX1670": "6"
#                                 }
#                             })

upload_statement(bank='tangerine',
                 account_ids=[
                     '3132333435363738393031323334353621dd20f68fd39fc584681e37b04c9738',
                     '31323334353637383930313233343536b07f7f8370bacc9575e1d614cd38d06a5d99f0cb4c4af76cd3ed4807a3d18dfb',
                 ],
                 secret_file='secrets/tangerine.json.gpg',
                 targets=[
                     {
                         "endpoint": "http://192.168.200.45:6060/import",
                         "user_id": "1",
                         "account_id_mapping": {
                             "3132333435363738393031323334353621dd20f68fd39fc584681e37b04c9738": "3",
                             "31323334353637383930313233343536b07f7f8370bacc9575e1d614cd38d06a5d99f0cb4c4af76cd3ed4807a3d18dfb": "1",
                         }
                     },
                     {
                         "endpoint": "http://192.168.200.45:9000/api/import",
                         "account_id_mapping": {
                             "3132333435363738393031323334353621dd20f68fd39fc584681e37b04c9738": "1",
                             "31323334353637383930313233343536b07f7f8370bacc9575e1d614cd38d06a5d99f0cb4c4af76cd3ed4807a3d18dfb": "4",
                         }
                     },
                 ])

# notify_rogersbank_transactions(account_ids=['XXXX1234'], secret_file='secrets/rogersbank.json.gpg', recipient='kevin.jing.qiu@gmail.com')

# import json
# import logging
# import datetime
# import subprocess
# from tangerine import TangerineClient, DictionaryBasedSecretProvider
# # from rogersbank import RogersBankClient, DictionaryBasedSecretProvider


# # FROM = datetime.date(2017, 6, 1)
# # TO = datetime.date(2017, 11, 2)


# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG)
#     output = subprocess.check_output(['gpg', '-d', 'secrets/tangerine.json.gpg'])
#     secret_provider = DictionaryBasedSecretProvider(json.loads(output))
#     client = TangerineClient(secret_provider)
#     # client = RogersBankClient(secret_provider)
#     from_ = datetime.datetime(2017, 12, 1)
#     to_ = datetime.datetime(2017, 12, 31)
#     with client.login():
#         accounts = [
#             acct for acct in client.list_accounts()
#         ]

#         import pdb; pdb.set_trace()  # XXX BREAKPOINT
#         print('fooo')

#         # for acct in accounts:
#         #     try:
#         #         client.download_ofx(acct, FROM, TO)
#         #     except UnsupportedAccountTypeForDownload as e:
#         #         print(e)
