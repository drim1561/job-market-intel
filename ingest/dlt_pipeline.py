"""dlt consumer: drain the Redpanda topic into Snowflake RAW.

dlt owns the load: it creates/evolves the RAW table, handles batching, and lands each
canonical posting as a row. We keep `raw_payload` as a single JSON column (not exploded
into child tables) so the original source record stays intact for later.

Landing is append-only: every poll appends current snapshots, which is exactly what the
dbt lifecycle model needs to compute first_seen / last_seen / repost_count over time.

Credentials: set the Snowflake env vars from .env (the helper below builds dlt's
connection string from them), or configure dlt's own secrets.toml.
"""

from __future__ import annotations

import json
import os
from typing import Iterator

import dlt
from confluent_kafka import Consumer


def _consume(
    topic: str,
    brokers: str,
    group: str = "jmi-loader",
    max_messages: int = 50_000,
    idle_polls: int = 5,
    poll_timeout: float = 2.0,
) -> Iterator[dict]:
    """Yield JSON-decoded messages until the topic is drained (idle_polls empty polls)."""
    consumer = Consumer(
        {
            "bootstrap.servers": brokers,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([topic])
    seen, idle = 0, 0
    try:
        while seen < max_messages and idle < idle_polls:
            msg = consumer.poll(poll_timeout)
            if msg is None:
                idle += 1
                continue
            if msg.error():
                continue
            idle = 0
            yield json.loads(msg.value())
            seen += 1
    finally:
        consumer.close()


@dlt.resource(
    name="job_postings",
    write_disposition="append",
    columns={"raw_payload": {"data_type": "json"}},  # keep as one JSON column, don't explode
)
def job_postings(topic: str, brokers: str):
    yield from _consume(topic, brokers)


def _snowflake_connection_string() -> str:
    """Build dlt's Snowflake connection string from the standard SNOWFLAKE_* env vars."""
    return (
        f"snowflake://{os.environ['SNOWFLAKE_USER']}:{os.environ['SNOWFLAKE_PASSWORD']}"
        f"@{os.environ['SNOWFLAKE_ACCOUNT']}/{os.environ['SNOWFLAKE_DATABASE']}"
        f"?warehouse={os.environ['SNOWFLAKE_WAREHOUSE']}&role={os.environ['SNOWFLAKE_ROLE']}"
    )


def run():
    """Drain the topic into <DATABASE>.RAW.job_postings. Returns the dlt load info."""
    from dotenv import load_dotenv

    load_dotenv()
    topic = os.environ.get("JOBS_TOPIC", "raw_job_postings")
    brokers = os.environ.get("REDPANDA_BROKERS", "localhost:19092")

    pipeline = dlt.pipeline(
        pipeline_name="job_market",
        destination=dlt.destinations.snowflake(credentials=_snowflake_connection_string()),
        dataset_name=os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
    )
    info = pipeline.run(job_postings(topic, brokers))
    print(info)
    return info


if __name__ == "__main__":
    run()
