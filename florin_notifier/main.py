import logging
import json
import datetime
import os
from rogersbank.client import RogersBankClient
from rogersbank.secret_provider import DictionaryBasedSecretProvider
import gnupg
from redis import Redis


def job():
    print('hello')


# def main():
#     while True:
#         schedule.run_pending()
#         time.sleep(1)


def create_provider(filename):
    gpg = gnupg.GPG(gnupghome=os.path.expanduser('~/.gnupg'))
    with open(filename) as f:
        crypt = gpg.decrypt(f.read())
    secret = json.loads(crypt.data.decode('ascii'))
    return DictionaryBasedSecretProvider(secret)


def new_transactions(previous, current):
    print('current: {}'.format(current))
    print('previoius: {}'.format(previous))


if __name__ == '__main__':
    logging.basicConfig(level='INFO')

    client = RogersBankClient(create_provider('rogersbank.json.gpg'))

    r = Redis()
    previous_scrapes = sorted(r.keys('scrape:rogersbank:*'))
    current_scrape_time = datetime.datetime.utcnow().isoformat()
    key = 'scrape:rogersbank:{}'.format(current_scrape_time)
    with client.login():
        current = client.recent_activities
        r.set(key, json.dumps(current))
    if len(previous_scrapes) < 1:
        previous = []
    else:
        previous = json.loads(r.get(previous_scrapes[-1]))
    print(new_transactions(previous, current))
