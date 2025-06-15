# Python SDK for the Arrowhead Framework

This is a Python SDK and CLI tool for the [Arrowhead Framework](https://arrowhead.eu), an Industrial IoT platform for service-oriented architecture. It provides both a command-line interface for managing Arrowhead systems and services, and an SDK for developing Arrowhead-compatible applications.

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
Follow the setup instructions in the [arrowhead-core-docker](https://github.com/johankristianss/arrowhead-core-docker) repository to deploy the core services.

**Note**: You must modify `/etc/hosts` as described in the instructions.

```bash
git clone https://github.com/johankristianss/arrowhead-core-docker.git
cd arrowhead-core-docker
docker-compose up -d
```

## Configuration

All configurations are managed using environment variables.

Create a file named `arrowhead.env` in the root of the `arrowhead-python-sdk` directory. Add the following content, replacing `XXXXX` with the absolute path to your `arrowhead-core-docker` directory:

```bash
export ARROWHEAD_VERBOSE="true"

# Certificates configuration
export ARROWHEAD_KEYSTORE_PASSWORD="123456"
export ARROWHEAD_ROOT_KEYSTORE="/XXXXX/arrowhead-core-docker/c1/certificates/master.p12"
export ARROWHEAD_ROOT_KEYSTORE_ALIAS="arrowhead.eu"
export ARROWHEAD_CLOUD_KEYSTORE="/XXXXX/arrowhead-core-docker/c1/certificates/c1.p12"
export ARROWHEAD_CLOUD_KEYSTORE_ALIAS="c1.ltu.arrowhead.eu"
export ARROWHEAD_SYSOPS_KEYSTORE="/XXXXX/arrowhead-core-docker/c1/certificates/sysop.p12"
export ARROWHEAD_TRUSTSTORE="/XXXXX/arrowhead-core-docker/c1/certificates/truststore.pem"

# Arrowhead Core Services configuration
export ARROWHEAD_TLS="true"
export ARROWHEAD_AUTHORIZATION_HOST="c1-authorization"
export ARROWHEAD_AUTHORIZATION_PORT="8445"
export ARROWHEAD_SERVICEREGISTRY_HOST="c1-serviceregistry"
export ARROWHEAD_SERVICEREGISTRY_PORT="8443"
export ARROWHEAD_ORCHESTRATOR_HOST="c1-orchestrator"
export ARROWHEAD_ORCHESTRATOR_PORT="8441"
```

Remember to source the `arrowhead.env` file to load the configurations:

```bash
source arrowhead.env
```

Try the Arrowhead CLI tool to verify your setup:

```bash
arrowhead systems ls
```

You should see output similar to this:

```console
╭────┬─────────────────┬────────────────────┬───────┬─────────────────────╮
│ ID │ System Name     │ Address            │ Port  │ Created             │
├────┼─────────────────┼────────────────────┼───────┼─────────────────────┤
│ 1  │ serviceregistry │ c1-serviceregistry │ 8443  │ 2023-11-20 12:00:00 │
│ 2  │ gateway         │ c1-gateway         │ 8453  │ 2023-11-20 12:00:00 │
│ 3  │ eventhandler    │ c1-eventhandler    │ 8455  │ 2023-11-20 12:00:00 │
│ 4  │ orchestrator    │ c1-orchestrator    │ 8441  │ 2023-11-20 12:00:00 │
│ 5  │ authorization   │ c1-authorization   │ 8445  │ 2023-11-20 12:00:00 │
│ 6  │ gatekeeper      │ c1-gatekeeper      │ 8449  │ 2023-11-20 12:00:00 │
╰────┴─────────────────┴────────────────────┴───────┴─────────────────────╯
```

## Tutorial: Developing Car Provider and Consumer Services

This tutorial will walk you through creating a complete Arrowhead application with a car factory provider service and a consumer that uses it. By the end, you'll have:

1. **Registered a car provider system** with proper certificate generation
2. **Registered a car consumer system** with proper certificate generation  
3. **Registered services** (`create-car` and `get-car`) with the service registry
4. **Set up authorization rules** allowing the consumer to access provider services
5. **Implemented the provider application** that offers car creation and listing services
6. **Implemented the consumer application** that consumes the car services
7. **Run the complete demo** showing end-to-end communication

### Step 1: Register the Car Provider System

Create a directory for the car provider and register it with Arrowhead:

```bash
mkdir carprovider
cd carprovider
arrowhead systems register --name carprovider --address localhost --port 8880
```

You should see output like this:

```console
✓ Certificate generated successfully: carprovider.p12
✓ Public key file created: carprovider.pub
✓ System 'carprovider' registered successfully with ID 7
Configuration saved to carprovider.env
```

The registration process creates several files:
- `carprovider.p12` - PKCS#12 certificate for the system
- `carprovider.pub` - Public key file
- `carprovider.env` - Environment configuration file

Let's verify the system was registered:

```bash
arrowhead systems ls
```

You should now see your carprovider system in the list:

```console
╭────┬─────────────────┬────────────────────┬───────┬─────────────────────╮
│ ID │ System Name     │ Address            │ Port  │ Created             │
├────┼─────────────────┼────────────────────┼───────┼─────────────────────┤
│ 1  │ serviceregistry │ c1-serviceregistry │ 8443  │ 2023-11-20 12:00:00 │
│ 2  │ gateway         │ c1-gateway         │ 8453  │ 2023-11-20 12:00:00 │
│ 3  │ eventhandler    │ c1-eventhandler    │ 8455  │ 2023-11-20 12:00:00 │
│ 4  │ orchestrator    │ c1-orchestrator    │ 8441  │ 2023-11-20 12:00:00 │
│ 5  │ authorization   │ c1-authorization   │ 8445  │ 2023-11-20 12:00:00 │
│ 6  │ gatekeeper      │ c1-gatekeeper      │ 8449  │ 2023-11-20 12:00:00 │
│ 7  │ carprovider     │ localhost          │ 8880  │ 2023-11-20 14:30:15 │
╰────┴─────────────────┴────────────────────┴───────┴─────────────────────╯
```

### Step 2: Register the Car Consumer System

Navigate back to the parent directory and create the consumer:

```bash
cd ..
mkdir carconsumer
cd carconsumer
arrowhead systems register --name carconsumer --address localhost --port 8881
```

You should see similar output:

```console
✓ Certificate generated successfully: carconsumer.p12
✓ Public key file created: carconsumer.pub
✓ System 'carconsumer' registered successfully with ID 8
Configuration saved to carconsumer.env
```

Verify both systems are now registered:

```bash
arrowhead systems ls
```

```console
╭────┬─────────────────┬────────────────────┬───────┬─────────────────────╮
│ ID │ System Name     │ Address            │ Port  │ Created             │
├────┼─────────────────┼────────────────────┼───────┼─────────────────────┤
│ 1  │ serviceregistry │ c1-serviceregistry │ 8443  │ 2023-11-20 12:00:00 │
│ 2  │ gateway         │ c1-gateway         │ 8453  │ 2023-11-20 12:00:00 │
│ 3  │ eventhandler    │ c1-eventhandler    │ 8455  │ 2023-11-20 12:00:00 │
│ 4  │ orchestrator    │ c1-orchestrator    │ 8441  │ 2023-11-20 12:00:00 │
│ 5  │ authorization   │ c1-authorization   │ 8445  │ 2023-11-20 12:00:00 │
│ 6  │ gatekeeper      │ c1-gatekeeper      │ 8449  │ 2023-11-20 12:00:00 │
│ 7  │ carprovider     │ localhost          │ 8880  │ 2023-11-20 14:30:15 │
│ 8  │ carconsumer     │ localhost          │ 8881  │ 2023-11-20 14:31:20 │
╰────┴─────────────────┴────────────────────┴───────┴─────────────────────╯
```

### Step 3: Register Services

Now we need to register the services that the car provider will offer. Register the `create-car` service:

```bash
arrowhead services register --system carprovider --definition create-car --uri /carfactory --method POST
```

```console
✓ Service 'create-car' registered successfully with ID 1

┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Property           ┃ Value       ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Service ID         │  1          │
│ Service Definition │ create-car  │
│ Provider System    │ carprovider │
│ Service URI        │ /create-car │
│ HTTP Method        │ POST        │
│ Security           │ TOKEN       │
│ Version            │ 1           │
└────────────────────┴─────────────┘
```

Register the `get-car` service:

```bash
arrowhead services register --system carprovider --definition get-car --uri /carfactory --method GET
```

```console
✓ Service 'get-car' registered successfully with ID 2

┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Property           ┃ Value       ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Service ID         │  2          │
│ Service Definition │ get-car     │
│ Provider System    │ carprovider │
│ Service URI        │ /get-car    │
│ HTTP Method        │ GET         │
│ Security           │ TOKEN       │
│ Version            │ 1           │
└────────────────────┴─────────────┘
```

Verify the services are registered:

```bash
arrowhead services ls
```

```console
┏━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ ID ┃ Service Definition ┃ Provider    ┃ URI         ┃ Method  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━┩
│ 1  │ create-car         │ carprovider │ /create-car │ POST    │
│ 2  │ get-car            │ carprovider │ /get-car    │ GET     │
└────┴────────────────────┴─────────────┴─────────────┴─────────┘
```

### Step 4: Set Up Authorization Rules

The consumer needs permission to access the provider's services. Add authorization for the `create-car` service:

```bash
arrowhead auths add --consumer carconsumer --provider carprovider --service create-car
```

```console
Authorization rule added with ID 1
```

Add authorization for the `get-car` service:

```bash
arrowhead auths add --consumer carconsumer --provider carprovider --service get-car
```

```console
Authorization rule added with ID 2
```

Verify the authorization rules:

```bash
arrowhead auths ls
```

```console
┏━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ ID ┃ Consumer    ┃ Provider    ┃ Service     ┃
┡━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ 1  │ carconsumer │ carprovider │ create-car  │
│ 2  │ carconsumer │ carprovider │ get-car     │
└────┴─────────────┴─────────────┴─────────────┘
```

### Step 5: Test Orchestration (Optional)

You can test the orchestration to verify everything is configured correctly using the improved `orchestrate` command. This command supports explicit flags that allow you to test orchestration on behalf of any system without needing to source specific environment files:

```bash
# Test orchestration using the carconsumer's certificate
arrowhead orchestrate --service create-car \
    --system carconsumer \
    --address localhost \
    --port 8881 \
    --keystore ./carconsumer/carconsumer.p12 \
    --password 123456 \
    --compact
```

Expected output:
```console
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Provider    ┃ Address           ┃ URI                                  ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ carprovider │ localhost:8880    │ /carprovider/create-car              │
└─────────────┴───────────────────┴──────────────────────────────────────┘
```

The flags allow you to:
- `--system`: Specify which system is making the orchestration request
- `--address`/`--port`: Set the requester's network details  
- `--keystore`/`--password`: Use a specific certificate for authentication
- `--compact`: Get a simplified output format

This makes it easy to test service discovery and authorization from any consumer system.

### Step 6: Provider Implementation

Navigate to the carprovider directory and create the provider application.

```bash
cd ../carprovider
```

Create a file named `provider.py` and add the following code:

```python
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


@system("carprovider")
class CarFactoryProvider:
    """Car factory provider system using high-level decorator API."""

    def __init__(self):
        # No key management needed - system name comes from decorator
        self.cars: List[Car] = []

    @service("create-car", method="POST", endpoint="/carfactory")
    def create_car(self, payload):
        """Create a new car."""
        logger.info("Creating car")
        
        # Payload is automatically parsed from JSON
        car = Car(**payload)
        logger.info(f"Creating car: {car}")
        
        self.cars.append(car)
        
        return {"status": "success", "message": "Car created successfully"}

    @service("get-car", method="GET", endpoint="/carfactory")
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
```

### Step 7: Consumer Implementation

Navigate to the carconsumer directory and create the consumer application.

```bash
cd ../carconsumer
```

Create a file named `consumer.py` and add the following code:

```python
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
    framework = None
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
        if framework:
            framework.close()
```

### Step 8: Run the Demo

Now you can run the complete demo to see the Arrowhead communication in action.

**Terminal 1 - Start the Provider:**

```bash
cd carprovider
source carprovider.env
python provider.py
```

You should see output like:

```console
INFO:__main__:Car factory provider started. Listening for requests...
INFO:werkzeug: * Running on https://localhost:8880
```

**Terminal 2 - Run the Consumer:**

Open a new terminal and run:

```bash
cd carconsumer
source carconsumer.env
python consumer.py
```

You should see output like:

```console
INFO:__main__:Car consumer started. Sending requests...
INFO:__main__:Creating car: Car(brand='Toyota', color='Red')
INFO:__main__:Create response: {"status": "success", "message": "Car created successfully"}
INFO:__main__:Creating car: Car(brand='Honda', color='Blue')
INFO:__main__:Create response: {"status": "success", "message": "Car created successfully"}
INFO:__main__:Fetching all cars...
INFO:__main__:Retrieved cars:
  Toyota - Red
  Honda - Blue
INFO:__main__:Consumer completed successfully
```

**Congratulations!** 🎉 You have successfully created and run a complete Arrowhead application with service provider and consumer communication. The cars are being created on the provider side and retrieved by the consumer through the Arrowhead Framework's service orchestration.


## Features

- **Simple Decorator API**: Use `@system` and `@service` decorators for rapid development
- **CLI Tool**: Command-line interface for managing Arrowhead systems, services, and authorizations
- **Automatic Registration**: Services are registered automatically with proper naming
- **TLS Support**: Full mutual TLS authentication using PKCS#12 certificates
- **JSON Handling**: Automatic JSON parsing and response formatting
- **Method Detection**: Auto-detects HTTP methods based on function signatures
- **Remote Deployment**: Works with both local and remote Arrowhead deployments

## Architecture

The Python SDK maintains the same core architecture as the Go version while providing a simpler decorator-based interface:

- **Decorator API**: Use `@system` and `@service` decorators to mark classes and methods
- **Core Models**: Pydantic-based data models for all Arrowhead entities
- **RPC Layer**: HTTP client with mutual TLS for core service communication
- **Framework**: Underlying engine for service registration and orchestration
- **Security**: Certificate management with OpenSSL/keytool support
- **CLI**: Click-based command-line interface with rich output formatting

## Security

The framework supports full mutual TLS authentication:

- PKCS#12 certificate loading
- Certificate chain validation
- JWT/JWE token handling
- OpenSSL and Java keytool integration

## Development

### Requirements

- Python 3.8+
- requests
- cryptography
- click
- flask
- pydantic
- rich
- flask-cors

### Testing

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black .
isort .
flake8
mypy .
```

## API Compatibility

This Python SDK maintains semantic compatibility with the Go version while providing a more Pythonic interface:

- **Decorator Pattern**: Python-specific `@system` and `@service` decorators for simplicity
- **Method Names**: CamelCase → snake_case (`SendRequest` → `send_request`)
- **Data Models**: Go structs → Pydantic models with automatic validation
- **Error Handling**: Go errors → Python exceptions with proper context
- **Unique Keys**: Each system instance requires a unique key for identification

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Related Projects

- [Arrowhead Framework](https://arrowhead.eu) - Official Arrowhead Framework
- [Go SDK](https://github.com/johankristianss/arrowhead) - Original Go implementation
