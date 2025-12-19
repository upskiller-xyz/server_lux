from typing import List, Any
import asyncio


class ParallelRequest:
    @classmethod
    def run(cls, func: Any, params: List[Any] = []) -> List[Any]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(func(*params))
        finally:
            loop.close()
        return results