help:
	echo "Welcome to lighthouse!"

build:
	docker build -t simonmok/lighthouse .

test: build
	docker run --rm simonmok/lighthouse pytest test.py

docker-push: test
	docker push simonmok/lighthouse