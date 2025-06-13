#!/usr/bin/env python3
"""
Example Arrowhead consumer application.

This example demonstrates how to consume services using the
Python Arrowhead Framework SDK.
"""

import json
import logging
from dataclasses import dataclass

from arrowhead import Framework, Params

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Car:
    """Car data model."""
    brand: str
    color: str


def main():
    """Main consumer application."""
    try:
        # Create framework instance for sending requests
        framework = Framework.create_framework()

        logger.info("Car consumer started. Sending requests...")

        # Create a car
        car = Car(brand="Toyota", color="Red")
        car_json = json.dumps({"brand": car.brand, "color": car.color})

        create_params = Params(query_params={}, payload=car_json.encode("utf-8"))

        logger.info(f"Creating car: {car}")
        response = framework.send_request("create-car", create_params)
        logger.info(f"Create response: {response.decode('utf-8')}")

        # Create another car
        car2 = Car(brand="Honda", color="Blue")
        car2_json = json.dumps({"brand": car2.brand, "color": car2.color})

        create_params2 = Params(query_params={}, payload=car2_json.encode("utf-8"))

        logger.info(f"Creating car: {car2}")
        response = framework.send_request("create-car", create_params2)
        logger.info(f"Create response: {response.decode('utf-8')}")

        # Fetch all cars
        get_params = Params.empty()

        logger.info("Fetching all cars...")
        response = framework.send_request("get-car", get_params)

        # Parse and display the cars
        cars_data = json.loads(response.decode("utf-8"))
        cars = [Car(**car_data) for car_data in cars_data]

        logger.info("Retrieved cars:")
        for car in cars:
            print(f"  {car.brand} - {car.color}")

        logger.info("Consumer completed successfully")

    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Consumer error: {e}")
        raise
    finally:
        if "framework" in locals():
            framework.close()


if __name__ == "__main__":
    main()
