import os
import logging
import yaml
from celery import Celery
from celery.schedules import crontab
from .tasks import notify_new_transactions as _notify_new_transactions


app = Celery()


notify_new_transactions = app.task(_notify_new_transactions)


logging.basicConfig(level='INFO')


@app.on_after_configure.connect
def setup(sender, **kwargs):
    config_file = os.getenv('CONFIG_FILE')
    assert config_file is not None

    with open(config_file) as f:
        config = yaml.load(f)

    for job in config['jobs']:
        fn = globals()[job['type']]
        ct = crontab(**job['schedule'])
        sender.add_periodic_task(ct, fn.s(**job['args']))

    # sender.add_periodic_task(
    #     crontab(hour="*/1"),
    #     notify_new_transactions.s('Rogers Mastercard', 'rogersbank.json.gpg', 'kevin.jing.qiu@gmail.com'))
