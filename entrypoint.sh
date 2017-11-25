#! /bin/sh
gpg --import /root/id.gpg.key
exec pipenv run celery -A florin_notifier.scheduler -b redis://$REDIS_HOST:$REDIS_PORT worker -B -l INFO
