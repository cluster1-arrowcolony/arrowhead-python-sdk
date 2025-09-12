# serial-number-generator/main.py
import asyncio
import logging

from arrowhead import System, Request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

serial_counter = 1
system = System(name="serialgenerator", port=8882, address="localhost")

@system.service(name="generate-serial-number", method="POST", endpoint="/generate")
async def generate_serial_number(_: Request) -> Response:
    global serial_counter
    logger.info("Handling request to generate serial number")
    
    current_serial = serial_counter
    serial_counter += 1
    
    logger.info(f"Generated serial number: {current_serial}")
    return Response({"serial_number": current_serial})

logger.info(f"Starting serial number generator '{system.name}' on {system.address}:{system.port}...")
asyncio.run(system.run())