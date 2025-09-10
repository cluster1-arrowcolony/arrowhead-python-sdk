# Python SDK for the Arrowhead Framework

This is a Python SDK and CLI tool for the [Arrowhead Framework](https://arrowhead.eu), an Industrial IoT platform for service-oriented architecture.

## Features

- **Asynchronous API**: Built on `asyncio` and `httpx` for high-performance, non-blocking I/O.
- **Robust `Request` -> `Response` API**: Define services with a clean `@app.service` decorator and a clear, explicit flow using `Request` and `Response` objects.
- **CLI Tool**: Command-line interface for managing Arrowhead systems, services, and authorizations.
- **Automatic Registration**: Services are registered automatically with proper naming.
- **Mutual TLS Support**: Full mTLS authentication using PKCS#12 certificates.
- **Direct Payload Access**: Service handlers receive the raw `bytes` of the request body, allowing for universal support of any content type (JSON, images, etc.).

## Installation

### 1. Requirements
* Python 3.8+.

### 2. Clone and Install the SDK
Clone this repository and install the `arrowhead` CLI tool in editable mode:

```bash
git clone https://github.com/your-repo/arrowhead-python-sdk.git
cd arrowhead-python-sdk
pip install -e .
```

### 3. Deploy Arrowhead Core Services
This SDK is compatible with both the standard Java-based Arrowhead Core systems and the lightweight `arrowhead-lite` Go implementation.

* **For `arrowhead-lite` (Recommended for local development):**
  Follow the setup instructions in the `arrowhead-lite` repository to generate certificates and run the server.

* **For Java Arrowhead Core:**
  Follow the setup instructions in the [arrowhead-core-docker](https://github.com/johankristianss/arrowhead-core-docker) repository.

## Configuration

All configurations are managed using environment variables. Create a file named `arrowhead-lite.env` (or similar) in the root of this project.

**Example for `arrowhead-lite`:**

```bash
# General SDK settings
export ARROWHEAD_VERBOSE="true"

# --- Certificate Configuration ---
# Absolute path to your certs directory (e.g., arrowhead-lite/certs)
CERTS_DIR="/path/to/your/certs"

# Sysop certificate for management tasks
export ARROWHEAD_SYSOPS_KEYSTORE="${CERTS_DIR}/sysop.p12"

# Truststore containing the CA that signed the server and client certs
export ARROWHEAD_TRUSTSTORE="${CERTS_DIR}/truststore.pem"

# Universal password for all keystores
export ARROWHEAD_KEYSTORE_PASSWORD="123456"

# CA Configuration for registering new systems
export ARROWHEAD_ROOT_KEYSTORE="${CERTS_DIR}/ca.p12"
export ARROWHEAD_ROOT_KEYSTORE_ALIAS="ArrowheadLiteLocalCA"
export ARROWHEAD_CLOUD_KEYSTORE="${CERTS_DIR}/ca.p12"
export ARROWHEAD_CLOUD_KEYSTORE_ALIAS="ArrowheadLiteLocalCA"

# --- Arrowhead Lite Core Service Configuration ---
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

## Tutorial: Developing a Multi-System Arrowhead Application

This tutorial walks you through creating an Arrowhead-based car manufacturing system consisting of three components:
1. A **Serial Number Generator**: Provides unique serial numbers.
2. A **Car Provider**: Creates cars and assigns them unique serial numbers provided by the **Serial Number Generator**.
3. A **Car Consumer**: Orders cars from the **Car Provider**.

### Step 0: Prepare the Environment

Create a Python virtual environment and install the SDK:

```bash
python -m venv venv
source venv/bin/activate
pip install .
```

### Step 1: Register Systems
The `arrowhead systems register` command creates the necessary certificates and registers the system with the Service Registry in one step.

```bash
# Ensure your environment variables are loaded
source arrowhead-lite.env

# Create the serial number generator system
mkdir serial-number-generator
cd serial-number-generator
arrowhead systems register --name serialgenerator --address localhost --port 8882
cd ..

# Create the car provider system
mkdir carprovider
cd carprovider
arrowhead systems register --name carprovider --address localhost --port 8880
cd ..

# Create the consumer system
mkdir carconsumer
cd carconsumer
arrowhead systems register --name carconsumer --address localhost --port 8881
cd ..

# Verify all systems are registered
arrowhead systems ls
```

### Step 2: Register Services
Register the services each system will provide.

```bash
arrowhead services register --system serialgenerator --definition generate-serial-number --uri /generate --method POST
arrowhead services register --system carprovider --definition create-car --uri /carfactory --method POST
arrowhead services register --system carprovider --definition get-cars --uri /carfactory --method GET

# Verify all services are registered
arrowhead services ls
```

### Step 3: Set Up Authorization Rules
Configure which systems can consume services from other systems.

```bash
# Allow carconsumer to access carprovider's services
arrowhead auths add --consumer carconsumer --provider carprovider --service create-car
arrowhead auths add --consumer carconsumer --provider carprovider --service get-cars

# Allow carprovider to access serialgenerator's service
arrowhead auths add --consumer carprovider --provider serialgenerator --service generate-serial-number

# Verify authorizations
arrowhead auths ls
```

### Step 4: Serial Number Generator Implementation
Navigate to the `serial-number-generator` directory and create `main.py`.

```python
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
```

### Step 5: Car Provider System Implementation
Navigate to the `carprovider` directory and create `main.py`.

```python
# carprovider/main.py
import asyncio
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
asyncio.run(system.run())
```

### Step 6: Car Consumer System Implementation
Navigate to the `carconsumer` directory and create `main.py`.

```python
# carconsumer/main.py
import asyncio
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

async def main():
    async with System(name="carconsumer", port=8881, address="localhost") as system:
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
    asyncio.run(main())
except KeyboardInterrupt:
    logger.info("Consumer stopped by user")
except Exception as e:
    logger.info(f"Error: {e}")
```

### Step 7: Run the Multi-System Demo

Now you can run the complete multi-system demo in three separate terminal windows.

**Terminal 1 - Start the Serial Generator:**
Navigate to the `serial-number-generator` directory, source its environment file, and run the Python script.

```bash
source venv/bin/activate
cd serial-number-generator
source serialgenerator.env
python main.py
```

**Terminal 2 - Start the Car Provider:**
Navigate to the `carprovider` directory, source its environment file, and run the Python script.

```bash
source venv/bin/activate
cd carprovider
source carprovider.env
python main.py
```

**Terminal 3 - Run the Consumer:**
Open a new terminal, navigate to the `carconsumer` directory, source its environment file, and run the script.

```bash
source venv/bin/activate
cd carconsumer
source carconsumer.env
python main.py
```
Output:
```
INFO:__main__:Car consumer started. Sending requests...
INFO:__main__:Requesting to create car: Car(brand='Toyota', color='Red')
INFO:__main__:Got response: {"status": "success", "message": "Car 'Toyota' created with serial number 1.", "serial_number": 1}
INFO:__main__:Retrieving cars...
INFO:__main__:Retrieved cars:
  - Toyota (Red) - Serial: 1
```

## CLI Reference

The `arrowhead` CLI provides comprehensive management capabilities for Arrowhead Framework systems, services, and authorizations.

```bash
# List all registered systems
arrowhead systems ls

# Get detailed system information
arrowhead systems get --id <system_id>

# Register new system
arrowhead systems register --name <name> --address <addr> --port <port>

# Unregister a system
arrowhead systems unregister --id <system_id>

# List all registered services
arrowhead services ls

# Get detailed service information
arrowhead services get --id <service_id>

# Register service
arrowhead services register --system <provider> --definition <service> --uri <path> --method <method>

# Unregister a service
arrowhead services unregister --id <service_id>

# List all authorization rules
arrowhead auths ls

# Add authorization rule
arrowhead auths add --consumer <consumer> --provider <provider> --service <service>

# Remove authorization rule
arrowhead auths remove --id <auth_id>

# Find authorized providers for service
arrowhead orchestrate --service <service_name>

# Orchestrate from specific context
arrowhead orchestrate --service <name> --system <sys> --address <addr> --port <port>

# Generate PKCS#12 certificate for system
arrowhead certs gen --name <system_name>

# Convert PKCS#12 to PEM format
arrowhead certs convert --p12-file <certificate.p12>

# Show CLI version information
arrowhead version

# Show environment configuration
arrowhead env

# Get help for any command
arrowhead <command> --help
```

## SDK Reference

The Python SDK provides a simple API for building Arrowhead systems that can both provide and consume services.

### System Class

**Create a system:**
```python
from arrowhead import System

# Create system instance
system = System(name="my-system", port=8080, address="localhost")
```

**System parameters:**
- `name`: System name (required)
- `port`: Port number (required) 
- `address`: Network address (required)

### Service Provider

**Register service endpoints with the `@system.service` decorator:**
```python
from arrowhead import Request, Response

@system.service("service-name", method="POST", endpoint="/my-endpoint")
async def my_service(request: Request) -> Response:
    # Handle the service request
    # Access payload, query_params, path_params, and headers from the request object
    return Response({"result": "success"})
```

**Service decorator parameters:**
- `service_name`: Service definition name
- `method`: HTTP method ("GET", "POST", "PUT", "DELETE")
- `endpoint`: URL path (supports path parameters like `/users/{user_id}`)

**Service handler function:**
- `request: Request`: An object containing the full request details.
- **Return**: An `arrowhead.Response` object.

### Service Consumer

**Send requests to other services:**
```python
# Send request without payload
response = await system.send_request("service-name")

# Send request with payload
payload = json.dumps({"key": "value"}).encode("utf-8")
response = await system.send_request("service-name", payload)

# Send request with query parameters
response = await system.send_request("service-name", params={"param1": "value1"})
```

**`send_request` parameters:**
- `service_def`: Service definition name to call
- `payload`: Request body as bytes (optional)
- `params`: Query parameters as dict (optional)
- **Returns**: Response body as bytes

### Running Systems

**Start a provider system:**
```python
# Run system (blocks until stopped)
asyncio.run(system.run())
```

**Use system as consumer:**
```python
async def main():
    async with System(name="consumer", port=8081, address="localhost") as system:
        response = await system.send_request("some-service")

asyncio.run(main())
```

### Complete Example

```python
import asyncio
import json
from arrowhead import System, Request, Response

# Create system
system = System(name="example-system", port=8080, address="localhost")

# Provide a service
@system.service("echo", method="POST", endpoint="/echo")
async def echo_service(request: Request) -> Response:
    data = json.loads(request.payload)
    return Response({"echo": data["message"]})

# Provide a service with path parameters
@system.service("get-user", method="GET", endpoint="/users/{user_id}")
async def get_user(request: Request) -> Response:
    user_id = request.path_params["user_id"]
    return Response({"user_id": user_id, "name": f"User {user_id}"})

# Start the system
asyncio.run(system.run())
```

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
