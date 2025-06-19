# Python SDK for the Arrowhead Framework

This is an asynchronous Python SDK and CLI tool for the [Arrowhead Framework](https://arrowhead.eu), an Industrial IoT platform for service-oriented architecture. It provides a command-line interface for management and a high-level SDK for developing performant, `async`-native Arrowhead applications.

## Features

- **Asynchronous API**: Built on `asyncio` and `httpx` for high-performance, non-blocking I/O.
- **Simple Decorator API**: Use `@system` and `@service` decorators for rapid provider development.
- **CLI Tool**: Command-line interface for managing Arrowhead systems, services, and authorizations.
- **Automatic Registration**: Services are registered automatically with proper naming.
- **Mutual TLS Support**: Full mTLS authentication using PKCS#12 certificates.
- **Type-Safe Models**: Pydantic models for all Arrowhead entities ensure data integrity.

## Installation

### 1. Install Python
Ensure you have Python 3.8+ installed.

### 2. Clone and Install the SDK
Clone this repository and install the `arrowhead` CLI tool in editable mode:

```bash
git clone https://github.com/your-repo/arrowhead-python-sdk.git
cd arrowhead-python-sdk
pip install -e .
```

### 3. Deploy Arrowhead Core Services
This SDK is compatible with both the standard Java-based Arrowhead Core systems and the lightweight `arrowhead-lite` Go implementation.

*   **For `arrowhead-lite` (Recommended for local development):**
    Follow the setup instructions in the `arrowhead-lite` repository to generate certificates and run the server.

*   **For Java Arrowhead Core:**
    Follow the setup instructions in the [arrowhead-core-docker](https://github.com/johankristianss/arrowhead-core-docker) repository.

## Configuration

All configurations are managed using environment variables. Create a file named `arrowhead-lite.env` (or similar) in the root of this project.

**Example for `arrowhead-lite`:**

```bash
# General SDK settings
export ARROWHEAD_VERBOSE="true"

# --- Certificate Configuration ---
# Absolute path to your arrowhead-lite/certs directory
CERT_DIR="/path/to/your/arrowhead-lite/certs"

# Sysop certificate for management tasks
export ARROWHEAD_SYSOPS_KEYSTORE="${CERT_DIR}/sysop.p12"

# Truststore containing the CA that signed the server and client certs
export ARROWHEAD_TRUSTSTORE="${CERT_DIR}/truststore.pem"

# Universal password for all keystores
export ARROWHEAD_KEYSTORE_PASSWORD="123456"

# CA Configuration for registering new systems
export ARROWHEAD_ROOT_KEYSTORE="${CERT_DIR}/ca.p12"
export ARROWHEAD_ROOT_KEYSTORE_ALIAS="ArrowheadLiteLocalCA"
export ARROWHEAD_CLOUD_KEYSTORE="${CERT_DIR}/ca.p12"
export ARROWHEAD_CLOUD_KEYSTORE_ALIAS="ArrowheadLiteLocalCA"

# --- Arrowhead Lite Core Service Configuration ---
export ARROWHEAD_TLS="true"
export ARROWHEAD_AUTHORIZATION_HOST="localhost"
export ARROWHEAD_AUTHORIZATION_PORT="8443"
export ARROWHEAD_SERVICEREGISTRY_HOST="localhost"
export ARROWHEAD_SERVICEREGISTRY_PORT="8443"
export ARROWHEAD_ORCHESTRATOR_HOST="localhost"
export ARROWHEAD_ORCHESTRATOR_PORT="8443"
```

**Note**: If you are connecting to `arrowhead-lite`, make sure all `ARROWHEAD_*_PORT` are set to `8443`, and all `ARROWHEAD_*_HOST` are set to the host where `./arrowhead-lite` is running (e.g., `localhost`).

Remember to source the file to load the configurations:

```bash
source arrowhead-lite.env
```

Try the Arrowhead CLI tool to verify your setup:

```bash
arrowhead systems ls
```

## Tutorial: Developing an Async Car Provider and Consumer

This tutorial walks you through creating a complete, asynchronous Arrowhead application.

### Step 1 & 2: Register Systems
The `arrowhead systems register` command creates the necessary certificates and registers the system with the Service Registry in one step.

```bash
# In one terminal, create the provider system
mkdir carprovider && cd carprovider
arrowhead systems register --name carprovider --address localhost --port 8880
cd ..

# In another terminal, create the consumer system
mkdir carconsumer && cd carconsumer
arrowhead systems register --name carconsumer --address localhost --port 8881
cd ..
```
Verify both systems are registered: `arrowhead systems ls`.

### Step 3: Register Services
Register the services the `carprovider` will offer.

```bash
arrowhead services register --system carprovider --definition create-car --uri /carfactory --method POST
arrowhead services register --system carprovider --definition get-car --uri /carfactory --method GET
```
Verify with `arrowhead services ls`.

### Step 4: Set Up Authorization Rules
Allow the `carconsumer` to access the `carprovider`'s services.

```bash
arrowhead auths add --consumer carconsumer --provider carprovider --service create-car
arrowhead auths add --consumer carconsumer --provider carprovider --service get-car
```
Verify with `arrowhead auths ls`.

### Step 5: Async Provider Implementation
Navigate to the `carprovider` directory and create `provider.py`. This code uses the `@system` and `@service` decorators to define an Arrowhead provider. Service handlers are now `async` functions.

```python
# carprovider/provider.py
import asyncio
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

@system("carprovider")
class CarFactoryProvider:
    """Car factory provider using the high-level decorator API."""

    def __init__(self):
        self.cars: List[Car] = []
        logger.info("CarFactoryProvider initialized")

    @service("create-car", method="POST", endpoint="/carfactory")
    async def create_car(self, payload: dict) -> dict:
        """Create a new car. The handler is now an async function."""
        logger.info("Handling async request to create-car")
        car = Car(**payload)
        logger.info(f"Creating car: {car}")
        self.cars.append(car)
        return {"status": "success", "message": "Car created successfully"}

    @service("get-car", method="GET", endpoint="/carfactory")
    async def get_cars(self) -> List[dict]:
        """Get all cars."""
        logger.info("Handling async request to get-car")
        return [asdict(car) for car in self.cars]

async def main():
    """Main async provider application."""
    car_factory = CarFactoryProvider()
    try:
        logger.info("Starting CarFactoryProvider...")
        # The start() method is now a coroutine and must be awaited.
        await car_factory.start()
    except KeyboardInterrupt:
        logger.info("Provider stopped by user")
    finally:
        logger.info("Stopping CarFactoryProvider...")
        # The stop() method is also a coroutine.
        await car_factory.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 6: Async Consumer Implementation
Navigate to the `carconsumer` directory and create `consumer.py`. This example uses an `async with` block to manage the framework's lifecycle.

```python
# carconsumer/consumer.py
import asyncio
import json
import logging
from dataclasses import asdict, dataclass

from arrowhead import Framework, Params

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Car:
    """Car data model."""
    brand: str
    color: str

async def main():
    """Main async consumer application."""
    # Use 'async with' for proper setup and teardown of the framework client.
    async with Framework.create_framework() as framework:
        try:
            logger.info("Car consumer started. Sending requests...")

            # Create a car
            car_to_create = Car(brand="Toyota", color="Red")
            create_params = Params(
                payload=json.dumps(asdict(car_to_create)).encode("utf-8")
            )

            logger.info(f"Creating car: {car_to_create}")
            # framework.send_request is now a coroutine.
            response = await framework.send_request("create-car", create_params)
            logger.info(f"Create response: {response.decode('utf-8')}")

            # Fetch all cars
            logger.info("Fetching all cars...")
            response = await framework.send_request("get-car")
            cars_data = json.loads(response.decode("utf-8"))
            cars = [Car(**car_data) for car_data in cars_data]

            logger.info("Retrieved cars:")
            for car in cars:
                print(f"  - {car.brand} ({car.color})")

        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
            raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
        logger.info("Consumer completed successfully")
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
```

### Step 7: Run the Demo

Now you can run the complete asynchronous demo.

**Terminal 1 - Start the Provider:**
Navigate to the `carprovider` directory, source its environment file, and run the Python script.

```bash
cd carprovider
source carprovider.env
python provider.py
```
Output:
```
INFO:__main__:Starting CarFactoryProvider...
INFO:arrowhead.decorators:Registered service: create-car at /carprovider/create-car
INFO:arrowhead.decorators:Registered service: get-car at /carprovider/get-car
INFO:arrowhead.decorators:Provider 'carprovider' started with 2 services
INFO:uvicorn:Started server process [12345]
...
```

**Terminal 2 - Run the Consumer:**
Open a new terminal, navigate to the `carconsumer` directory, source its environment file, and run the script.

```bash
cd carconsumer
source carconsumer.env
python consumer.py
```
Output:
```
INFO:__main__:Car consumer started. Sending requests...
INFO:__main__:Creating car: Car(brand='Toyota', color='Red')
INFO:__main__:Create response: {"status": "success", "message": "Car created successfully"}
INFO:__main__:Fetching all cars...
INFO:__main__:Retrieved cars:
  - Toyota (Red)
INFO:__main__:Consumer completed successfully
```

**Congratulations!** 🎉 You have successfully created and run a high-performance, fully asynchronous Arrowhead application.

## Development

### Requirements
- Python 3.8+
- `pip install -r requirements.txt`

### Testing
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting and type checking
black .
isort .
flake8
mypy .
```
