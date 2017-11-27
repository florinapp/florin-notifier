import json
import freezegun
import pytest
import mock
from mock import call
import contextlib
from redis import Redis
from florin_notifier.tasks import notify_tangerine_transactions


@pytest.fixture
def redis():
    r = Redis()
    for key in r.scan_iter("scrape:*"):
        r.delete(key)
    return r


@pytest.fixture
def tangerine_client():
    m = mock.Mock()

    @contextlib.contextmanager
    def fake_ctx_mgr():
        yield

    m.login = fake_ctx_mgr
    return m


@pytest.fixture
def email():
    return mock.Mock()


@pytest.fixture
def sendgrid_client():
    return mock.Mock()


@freezegun.freeze_time('2017-11-10T12:00:00')
def test_notify_tangerine_transactions___no_previous_scrapes(redis, tangerine_client, email):
    tangerine_client.list_transactions.return_value = []
    notify_tangerine_transactions(['12345', '45678'], 'SECRET', 'foo@example.com', tangerine_client, email)
    assert redis.keys('scrape:tangerine*') == [b'scrape:tangerine:2017-11-10T12:00:00']
    assert redis.get(b'scrape:tangerine:2017-11-10T12:00:00') == b'[]'


@freezegun.freeze_time('2017-11-10T12:00:00.1111')
def test_notify_tangerine_transactions___with_previous_scrape_on_a_different_day(redis, tangerine_client, email):
    txn_1 = {
        'transaction_date': '2017-11-01T07:17:03',
        'amount': -55.54,
        'description': 'BUY STUFF',
        'type': 'WITHDRAWAL',
        'account_id': '12345',
        'id': 123456789,
        'posted_date': '2017-11-04T00:00:00',
        'status': 'POSTED'
    }
    txn_2 = {
        'transaction_date': '2017-11-10T07:17:03',
        'amount': -100.99,
        'description': 'BUY STUFF #2',
        'type': 'WITHDRAWAL',
        'account_id': '12345',
        'id': 123456789,
        'posted_date': '2017-11-04T00:00:00',
        'status': 'POSTED'
    }
    redis.set('scrape:tangerine:2017-11-09T12:10:11', json.dumps([txn_1]))
    tangerine_client.list_transactions.return_value = [txn_2]
    notify_tangerine_transactions(['12345', '45678'], 'SECRET', 'foo@example.com', tangerine_client, email)
    assert redis.keys('scrape:tangerine*') == [
        b'scrape:tangerine:2017-11-09T12:10:11',
        b'scrape:tangerine:2017-11-10T12:00:00.111100']

    assert email.send_new_transaction_email.call_args_list == [call('foo@example.com', [txn_2])]
