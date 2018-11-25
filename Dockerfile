FROM python:3.6-alpine

RUN apk add build-base
RUN pip install pipenv

WORKDIR /app
COPY Pipfile .
RUN pipenv install --skip-lock --dev

COPY lighthouse .
WORKDIR /app/lighthouse

ENTRYPOINT ["pipenv", "run"]