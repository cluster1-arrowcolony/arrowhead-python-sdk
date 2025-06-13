#!/usr/bin/env python3
"""
Example Arrowhead provider application.

This example demonstrates how to create service providers using the
high-level decorator API of the Python Arrowhead Framework SDK.
"""

import logging
from dataclasses import asdict, dataclass
from typing import List

from arrowhead import system, service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Car:
    """Car data model."""
    brand: str
    color: str


@system("car-factory")
class CarFactoryProvider:
    """Car factory provider system using high-level decorator API."""

    def __init__(self):
        # Each system instance MUST have a unique key
        self.key = "provider"  # Could be "factory-01", "factory-02", etc.
        self.cars: List[Car] = []

    @service("create-car", method="POST")
    def create_car(self, payload):
        """Create a new car."""
        logger.info("Creating car")
        
        # Payload is automatically parsed from JSON
        car = Car(**payload)
        logger.info(f"Creating car: {car}")
        
        self.cars.append(car)
        
        return {"status": "success", "message": "Car created successfully"}

    @service("get-car")  # Auto-detects GET method (no payload parameter)
    def get_cars(self):
        """Get all cars."""
        logger.info("Retrieving all cars")
        
        # Convert cars to dictionaries for JSON response
        cars_data = [asdict(car) for car in self.cars]
        return cars_data


def main():
    """Main provider application."""
    try:
        # Create and start the car factory provider
        car_factory = CarFactoryProvider()
        
        logger.info("Car factory provider started. Listening for requests...")
        
        # Start the system (registers services and starts server)
        car_factory.start()

    except KeyboardInterrupt:
        logger.info("Provider stopped by user")
    except Exception as e:
        logger.error(f"Provider error: {e}")
        raise


if __name__ == "__main__":
    main()
