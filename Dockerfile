FROM python:3.6
ENV CONFIG_FILE config.yaml
ENV REDIS_HOST localhost
ENV REDIS_PORT 6379
COPY ["florin_notifier", "/app/florin_notifier"]
COPY ["Pipfile", "/app/Pipfile"]
COPY ["Pipfile.lock", "/app/Pipfile.lock"]
COPY ["entrypoint.sh", "/entrypoint.sh"]
RUN pip install pipenv \
    && ln -s $(which pip) /bin/pip \
    && cd /app \
    && pipenv install
WORKDIR /app
VOLUME ["/app/config.yaml", "/app/secrets", "/root/id.gpg.key"]
CMD /entrypoint.sh
