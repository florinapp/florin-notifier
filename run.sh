CONFIG_FILE=$(pwd)/config.yaml celery -A florin_notifier.scheduler -b redis://localhost:6379 worker -B -l INFO
