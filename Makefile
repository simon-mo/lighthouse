SHA_TAG=$(git rev-parse --verify --short=10 HEAD)

help:
	echo "Welcome to lighthouse!"

build:
	docker build -t simonmok/lighthouse:$(SHA_TAG) .

test: build
	docker run --rm simonmok/lighthouse:$(SHA_TAG) pytest test.py

docker-push: test
	docker push simonmok/lighthouse:$(SHA_TAG)

	docker tag -t simonmok/lighthouse:$(SHA_TAG) simonmok/lighthouse:latest
	docker push simonmok/lighthouse:latest