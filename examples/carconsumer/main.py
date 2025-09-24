import json
import logging
from dataclasses import asdict, dataclass

from arrowhead import System, Request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Car:
    brand: str
    color: str
    serial_number: int | None = None

system = System(name="carconsumer", port=8881, address="localhost")

@system.main()
async def main():
    logger.info("Car consumer started. Sending requests...")

    car = Car(brand="Toyota", color="Red")
    logger.info(f"Requesting to create car: {car}")

    response = await system.send("create-car", Request(payload=asdict(car)))

    logger.info(f"Got response: {json.dumps(response.content)}")

    logger.info("Retrieving cars...")
    response: Response = await system.send("get-cars", Request())
    cars_data = response.content
    cars = [Car(**car_data) for car_data in cars_data]

    logger.info("Retrieved cars:")
    for car in cars:
        logger.info(f"  - {car.brand} ({car.color}) - Serial: {car.serial_number}")

if __name__ == "__main__":
    try:
        system.run()
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
