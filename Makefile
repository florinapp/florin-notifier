build:
	docker build -t florin-notifier:$(shell git rev-parse HEAD) .

push:
	docker push florin-notifier:$(shell git rev-parse HEAD)
