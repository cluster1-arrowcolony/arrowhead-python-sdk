import logging
from dataclasses import asdict, dataclass
from typing import List

from arrowhead import System, Request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Car:
    brand: str
    color: str
    serial_number: int

cars: List[Car] = []
system = System(name="carprovider", port=8880, address="localhost")

@system.service(name="create-car", method="POST", endpoint="/carfactory")
async def create_car(request: Request) -> Response:
    logger.info("Handling request to create a car")
    if not request.payload:
        logger.error("No payload provided in the request")
        return Response({"status": "error", "message": "No payload provided."}, status_code=400)

    logger.info("Requesting serial number from serial generator service")
    response = await system.send("generate-serial-number", Request())

    new_car = Car(
        brand=request.payload["brand"], 
        color=request.payload["color"],
        serial_number=response.content["serial_number"]
    )
    cars.append(new_car)
    logger.info(f"Car created: {new_car}")

    return Response({
        "status": "success", 
        "message": f"Car '{new_car.brand}' created with serial number {new_car.serial_number}.",
        "serial_number": new_car.serial_number
    }, status_code=201)

@system.service(name="get-cars", method="GET", endpoint="/carfactory")
async def get_cars(_: Request) -> Response:
    logger.info("Handling request to get cars")
    return Response([asdict(car) for car in cars])

if __name__ == "__main__":
    logger.info(f"Starting provider '{system.name}' on {system.address}:{system.port}...")
    system.run()
