from typing import List, Any
import time
import asyncio
import logging
logger = logging.getLogger("logger")


class ParallelRequest:
    @classmethod
    def run(cls, func: Any, params:List[Any]=[])->List[Any]:
        loop_start = time.time()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        logger.info(f"⏱️  Event loop creation: {time.time() - loop_start:.3f}s")

        try:
            calc_start = time.time()
            results = loop.run_until_complete(
                func(*params)
            )
            logger.info(f"⏱️  Async calculation: {time.time() - calc_start:.3f}s")
        finally:
            loop.close()
        return results