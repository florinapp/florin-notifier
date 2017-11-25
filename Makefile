build:
	docker build -t kevinjqiu/florin-notifier:$(shell git rev-parse HEAD) .

push:
	docker push kevinjqiu/florin-notifier:$(shell git rev-parse HEAD)
