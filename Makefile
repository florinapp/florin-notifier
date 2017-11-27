build:
	docker build -t kevinjqiu/florin-notifier:$(shell git rev-parse HEAD) .

push:
	docker push kevinjqiu/florin-notifier:$(shell git rev-parse HEAD)


test:
	docker stop test-redis && docker rm test-redis || true
	docker run -d --name test-redis redis:4-alpine
	CONFIG_FILE=$$(pwd)/test-config.yaml py.test -v tests/
