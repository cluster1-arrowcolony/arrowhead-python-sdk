# carprovider/main.py
import json
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
    serial_number: str

cars: List[Car] = []
system = System(name="carprovider", port=8880, address="localhost")

@system.service(name="create-car", method="POST", endpoint="/carfactory")
async def create_car(request: Request) -> Response:
    logger.info("Handling request to create a car")
    if not request.payload:
        logger.error("No payload provided in the request")
        return Response({"status": "error", "message": "No payload provided."}, status_code=400)

    car_data = json.loads(request.payload)
    
    logger.info("Requesting serial number from serial generator service")
    serial_response = await system.send_request("generate-serial-number")
    serial_data = json.loads(serial_response.decode("utf-8"))
    serial_number = serial_data["serial_number"]
    logger.info(f"Received serial number: {serial_number}")
    
    new_car = Car(
        brand=car_data["brand"], 
        color=car_data["color"],
        serial_number=serial_number
    )
    cars.append(new_car)
    logger.info(f"Car created: {new_car}")
    
    return Response({
        "status": "success", 
        "message": f"Car '{new_car.brand}' created with serial number {serial_number}.",
        "serial_number": serial_number
    }, status_code=201)

@system.service(name="get-cars", method="GET", endpoint="/carfactory")
async def get_cars(_: Request) -> Response:
    logger.info("Handling request to get cars")
    return Response([asdict(car) for car in cars])

logger.info(f"Starting provider '{system.name}' on {system.address}:{system.port}...")
system.run()
