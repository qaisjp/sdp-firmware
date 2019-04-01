import asyncio
import logging as log
import sys
from remote import Remote, LogType


def run():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)

    # GrowBot 2
    r = Remote("e3dde6f2-5925-42e4-b37d-5214f18ae798", "ws://localhost:8080")
    print("Test")
    r.create_log_entry(LogType.UNKNOWN, "Hello, world!")
    print("Created")

    asyncio.ensure_future(r.connect())

    loop = asyncio.get_event_loop()
    pending = asyncio.Task.all_tasks()
    loop.run_until_complete(asyncio.gather(*pending))


if __name__ == "__main__":
    run()
    print("Completed!")
