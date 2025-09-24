import pytest

from arrowhead import Request, Simulator

import carprovider.main
import carconsumer.main
import serial_number_generator.main

@pytest.fixture(autouse=True)
def reset_state():
    carprovider.main.cars.clear()
    serial_number_generator.main.serial_counter = 1


async def test_integration():
    systems = [
        carconsumer.main.system,
        carprovider.main.system,
        serial_number_generator.main.system
    ]
    async with Simulator(systems) as sim:
        assert len(carprovider.main.cars) == 1
        car = carprovider.main.cars[0]
        assert car.brand == "Toyota"
        assert car.color == "Red"
        assert car.serial_number == 1

        response = await sim.send("generate-serial-number", Request())
        assert response.status_code == 200
        assert response.content["serial_number"] == 2

        await sim.send("create-car", Request(payload={"brand": "Toyota", "color": "Red"})) 
        response = await sim.send("get-cars", Request())
        assert response.status_code == 200
        assert len(response.content) == 2
        car2 = response.content[1]
        assert car2["brand"] == "Toyota"
        assert car2["color"] == "Red"
        assert car2["serial_number"] == 3
