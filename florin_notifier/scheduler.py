import logging
from celery import Celery
from celery.schedules import crontab
from .tasks import notify_new_transactions as _notify_new_transactions


app = Celery()


notify_new_transactions = app.task(_notify_new_transactions)


logging.basicConfig(level='INFO')


@app.on_after_configure.connect
def setup(sender, **kwargs):
    sender.add_periodic_task(
        crontab(minute="*/1"),
        notify_new_transactions.s('rogersbank.json.gpg', 'kevin.jing.qiu@gmail.com'))
