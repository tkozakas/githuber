FROM python:3.12-alpine

WORKDIR /app
COPY src/ .

ENV PYTHONUNBUFFERED=1
RUN mkdir /state
VOLUME /state

CMD ["python", "-m", "githuber"]
