"""
Icarus data ingestion worker.
Pulls market data from all sources on schedule, writes to TimescaleDB via Redis Streams.
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("icarus-worker")


async def main():
    log.info("Icarus worker starting")
    # Scheduler will be configured in Phase 1 (IC-005)
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
