"""Publish CanonicalPosting records to the Redpanda topic.

Sources fetch + map to CanonicalPosting; this module is the only thing that talks to
Redpanda. Keeping the transport in one place means a source never needs to know how
messages are delivered (and we could swap Redpanda out without touching sources).
"""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Iterable

from confluent_kafka import Producer

from .schema import CanonicalPosting


def get_producer(brokers: str | None = None) -> Producer:
    brokers = brokers or os.environ.get("REDPANDA_BROKERS", "localhost:19092")
    return Producer({"bootstrap.servers": brokers, "linger.ms": 50})


def publish(
    postings: Iterable[CanonicalPosting],
    producer: Producer | None = None,
    topic: str | None = None,
) -> int:
    """Publish postings; stamps ingested_at (UTC) if the source didn't. Returns count."""
    producer = producer or get_producer()
    topic = topic or os.environ.get("JOBS_TOPIC", "raw_job_postings")
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    count = 0
    for p in postings:
        p.setdefault("ingested_at", now)
        # Kafka key = source + source id, so the same listing lands on a stable partition.
        msg_key = f"{p.get('source', '')}:{p.get('source_posting_id', '')}".encode()
        producer.produce(topic, key=msg_key, value=json.dumps(p, default=str).encode())
        count += 1
        if count % 500 == 0:
            producer.poll(0)  # serve delivery callbacks so the buffer doesn't fill
    producer.flush()
    return count


if __name__ == "__main__":
    # Thin CLI: fetch from every configured source and publish. A source whose API key
    # isn't set (KeyError) or that errors out is skipped so the others still run; ATS
    # needs no keys, so it always runs.
    from dotenv import load_dotenv

    from .sources import adzuna, ats, usajobs

    load_dotenv()
    shared_producer = get_producer()
    total = 0
    for name, fetch in (("adzuna", adzuna.fetch), ("usajobs", usajobs.fetch), ("ats", ats.fetch)):
        try:
            n = publish(fetch(), producer=shared_producer)
            total += n
            print(f"  {name}: published {n}")
        except KeyError as missing:
            print(f"  {name}: skipped (missing env {missing})")
        except Exception as err:  # noqa: BLE001 - one bad source shouldn't stop the rest
            print(f"  {name}: error ({err.__class__.__name__}: {err})")
    print(f"published {total} postings to '{os.environ.get('JOBS_TOPIC', 'raw_job_postings')}'")
