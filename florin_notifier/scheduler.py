import os
import logging
from celery import Celery
from celery.schedules import crontab
from .tasks import notify_new_transactions as _notify_new_transactions
from .config import config


app = Celery()


notify_new_transactions = app.task(_notify_new_transactions)


logging.basicConfig(level='INFO')


@app.on_after_configure.connect
def setup(sender, **kwargs):
    for job in config['jobs']:
        fn = globals()[job['type']]
        ct = crontab(**job['schedule'])
        sender.add_periodic_task(ct, fn.s(**job['args']))