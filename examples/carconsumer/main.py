# carconsumer/main.py
import json
import logging
from dataclasses import asdict, dataclass

from arrowhead import System

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Car:
    brand: str
    color: str
    serial_number: str | None = None

system = System(name="carconsumer", port=8881, address="localhost")

@system.main()
async def main():
    car = Car(brand="Toyota", color="Red")
    logger.info(f"Requesting to create car: {car}")
    response = await system.send_request("create-car", json.dumps(asdict(car)).encode("utf-8"))
    logger.info("Car consumer started. Sending requests...")
    logger.info(f"Got response: {response.decode('utf-8')}")

    logger.info("Retrieving cars...")
    response = await system.send_request("get-cars")
    cars = [Car(**car_data) for car_data in json.loads(response.decode("utf-8"))]

    logger.info("Retrieved cars:")
    for car in cars:
        logger.info(f"  - {car.brand} ({car.color}) - Serial: {car.serial_number}")

try:
    system.run()
except KeyboardInterrupt:
    logger.info("Consumer stopped by user")
except Exception as e:
    logger.info(f"Error: {e}")
