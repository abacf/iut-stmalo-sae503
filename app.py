import time

import redis
import argparse
import uvicorn
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI, Depends
from fastapi.openapi.docs import get_swagger_ui_html

app: FastAPI = FastAPI()

# nombre de tentatives pour joindre Redis
n_retries = 3


def get_ticket_number():
    retries = n_retries
    while True:
        try:
            return cache.incr("ticket_number_" + args.queue_name)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


def create_ticket(ticket_number):
    retries = n_retries
    while True:
        try:
            return cache.lpush("queue_" + args.queue_name, ticket_number)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


def retrieve_ticket():
    retries = n_retries
    while True:
        try:
            return cache.rpop("queue_" + args.queue_name)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


def get_queue_size():
    retries = n_retries
    while True:
        try:
            return cache.llen("queue_" + args.queue_name)
        except redis.exceptions.ConnectionError as exc:
            if retries == 0:
                raise exc
            retries -= 1
            time.sleep(0.5)


@app.get("/get_ticket")
def get_ticket():
    ticket_number = get_ticket_number()
    create_ticket(ticket_number)
    queue_size = get_queue_size()
    return "Sure thing, your ticket has the number : {}. {} people are waiting".format(
        ticket_number, queue_size
    )


@app.get("/call_ticket")
def call_ticket():
    ticket_number = retrieve_ticket()
    queue_size = get_queue_size()
    if ticket_number is None:
        return "Queue is empty"
    else:
        return "Customer with ticket {}, please proceed ! {} people are waiting".format(
            ticket_number, queue_size
        )


@app.get("/list_tickets")
def list_tickets():
    queue_size = get_queue_size()
    return "{} people are waiting\n".format(queue_size)


@app.get("/docs")
def display_doc():
    return get_swagger_ui_html(title="SAE503", openapi_url="/openapi.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Webservice de gestion d'une file d'attente"
    )
    parser.add_argument(
        "--redis-host",
        dest="redis_host",
        help="Nom ou adresse IP du serveur Redis",
        default="127.0.0.1",
    )
    parser.add_argument(
        "--redis-port",
        dest="redis_port",
        help="Port TCP du serveur Redis",
        default=6379,
    )
    parser.add_argument(
        "--queue-name",
        dest="queue_name",
        help="Nom de la file d'attente",
        default="DEFAULT",
    )
    parser.add_argument("--env", dest="env", help="Environnement", default="dev")
    args = parser.parse_args()
    instrumentator = Instrumentator().instrument(
        app,
        metric_namespace=f"file_attente_{args.env}",
        metric_subsystem=args.queue_name,
    )
    cache = redis.Redis(host=args.redis_host, port=args.redis_port)
    instrumentator.expose(
        app, endpoint="/metrics", include_in_schema=True, should_gzip=True
    )
    uvicorn.run(app, host="0.0.0.0", port="8000", log_level="info")
