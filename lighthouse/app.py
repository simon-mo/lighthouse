import asyncio
import json
import logging
from time import time

import click
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, UJSONResponse
from starlette.websockets import WebSocketDisconnect, WebSocketState

from aiokafka import AIOKafkaConsumer, TopicPartition
from model import (
    create_build,
    get_build_dict,
    get_checkpoint_by_build_and_target,
    init_db,
    report_checkpoint,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
    datefmt="%y-%m-%d:%H:%M:%S",
    level=logging.INFO,
)

app = Starlette()
config = {}


@app.route("/api/build", methods=["POST"])
async def api_create_build(request: Request):
    env_var_dict = await request.json()
    try:
        create_build(env_var_dict)
        return UJSONResponse({"success": "true"})
    except Exception as e:
        return UJSONResponse({"success": "false", "error": str(e)})


@app.route("/api/build/{jenkins_tag}", methods=["GET"])
async def api_get_build(request: Request):
    tag = request.path_params["jenkins_tag"]
    return UJSONResponse(get_build_dict(tag))


@app.route("/api/checkpoint/{build}/{target}/{start_or_finish}", methods=["POST"])
async def api_create_checkpoint(request: Request):
    try:
        build = request.path_params["build"]
        target = request.path_params["target"]
        start_or_finish = request.path_params["start_or_finish"]

        if start_or_finish not in ["start", "finish"]:
            return UJSONResponse(
                {
                    "success": "false",
                    "error": "api must be called with /api/checkpoint/start or /api/checkpoint/finish",
                },
                status_code=400,
            )

        report_checkpoint(
            build,
            time(),
            start_or_finish,
            target,
            request.query_params.get("exit_code", None),
        )
        return UJSONResponse({"success": "true"})
    except Exception as e:
        return UJSONResponse({"success": "false", "error": str(e)}, status_code=500)


@app.route("/api/checkpoint/{build}/{target}", methods=["GET"])
async def api_get_checkpoint(request: Request):
    build = request.path_params["build"]
    target = request.path_params["target"]
    if build == "*" and target == "*":
        return UJSONResponse(
            {
                "success": "false",
                "error": "must specify at least one of build or target",
            },
            status_code=400,
        )
    return UJSONResponse(get_checkpoint_by_build_and_target(build, target))


async def get_consumer():
    return AIOKafkaConsumer(
        bootstrap_servers=config["kafka_addr"], loop=asyncio.get_event_loop()
    )


@app.on_event("startup")
async def init_default_consumer():
    consumer = await get_consumer()
    await consumer.start()
    config["default_consumer"] = consumer


@app.on_event("shutdown")
async def clean_up_default_consumer():
    await config["default_consumer"].stop()


@app.route("/")
async def index(request):
    consumer = config["default_consumer"]
    all_topics = await consumer.topics()
    # TODO(Simon): Sort topics by latest offset time.
    all_topics_url = [request.url_for("by_build", topic=topic) for topic in all_topics]
    return UJSONResponse(all_topics_url)


@app.route("/log/{topic}")
async def by_build(request):
    return FileResponse("tempaltes/log_view.html")


@app.websocket_route("/ws/{topic}")
async def send_all_by_build(websocket):
    await websocket.accept()
    await consume_by_topic(websocket, websocket.path_params["topic"])
    await websocket.close()


async def consume_by_topic(websocket, topic):
    consumer = await get_consumer()
    await consumer.start()
    tp = TopicPartition(topic, 0)
    consumer.assign([tp])

    current_offsets = await consumer.end_offsets([tp])
    target_offset = current_offsets[tp] - 200
    target_offset = 0 if target_offset < 0 else target_offset
    consumer.seek(tp, target_offset)

    try:
        counter = 0
        while websocket.client_state == WebSocketState.CONNECTED:
            msg_dict = await consumer.getmany(tp)

            for _, msgs in msg_dict.items():
                item_cnt = len(msgs)
                if item_cnt:
                    logging.info(f"retrieved {item_cnt} items at once")
                for msg in msgs:
                    await websocket.send_text(
                        json.dumps(
                            {"message": msg.value.decode(), "timestamp": msg.timestamp}
                        )
                    )

            counter += 1
            if counter % 10 == 0:
                await websocket.send_text("ping")
                await websocket.receive_text()
    except WebSocketDisconnect as e:
        logging.info("Exited", e)
    finally:
        await consumer.stop()


@click.command()
@click.option(
    "--kafka-address", "-a", help="Kafka Bootstrap Server Address", required=True
)
@click.option("--db-path", help="Path for sqlite database", default="db.sqlite")
@click.option("--debug/--no-debug", "-d", default=False)
@click.option("--host", "-h", default="0.0.0.0")
@click.option("--port", "-p", type=int, default=8000)
def cli_entry(kafka_address, db_path, debug, host, port):
    app.debug = debug
    # "ci.simon-mo.com:32775"
    config["kafka_addr"] = kafka_address
    init_db(db_path, debug)
    uvicorn.run(app, host=host, port=port, debug=debug)


if __name__ == "__main__":
    cli_entry()
