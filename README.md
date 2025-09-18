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

All configurations are managed using environment variables. A template configuration file `arrowhead.env` is provided in the repository root.

**Setup:**

1. Copy and customize the configuration file:
   ```bash
   cp arrowhead.env my-arrowhead.env
   ```

2. Edit `my-arrowhead.env` and update the `CERTS_DIR` path to point to your certificates directory:
   ```bash
   # Change this line to your actual certificates path
   CERTS_DIR="/path/to/your/certs"
   ```

**Note**: If you are connecting to `arrowhead-lite`, make sure all `ARROWHEAD_*_PORT` are set to `8443`, and all `ARROWHEAD_*_HOST` are set to the host where `./arrowhead-lite` is running (e.g., `localhost`).

Remember to source the file to load the configurations:

```bash
source my-arrowhead.env
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

**Note**: Complete implementation examples for all three services are available in the `examples/` directory.

### Step 0: Prepare the Environment

Create a Python virtual environment and install the SDK:

```bash
python -m venv venv
source venv/bin/activate
pip install .
```

### Step 1: Register Systems
The `arrowhead systems register` command creates the necessary certificates and registers the system with the Service Registry in one step. Run each command from the respective examples directory so certificates are generated in the correct location.

```bash
# Ensure your environment variables are loaded
source my-arrowhead.env

# Register the serial number generator system
cd examples/serial_number_generator
arrowhead systems register --name serialgenerator --address localhost --port 8882
cd ../..

# Register the car provider system
cd examples/carprovider
arrowhead systems register --name carprovider --address localhost --port 8880
cd ../..

# Register the consumer system
cd examples/carconsumer
arrowhead systems register --name carconsumer --address localhost --port 8881
cd ../..

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

### Step 4: Implementation Files
The complete implementations for all three services are available in the `examples/` directory:

- **`examples/serial-number-generator/main.py`** - A simple service that generates unique sequential serial numbers via a POST endpoint `/generate`. Maintains an internal counter and returns JSON responses with the next available serial number.

- **`examples/carprovider/main.py`** - A car manufacturing service that provides two endpoints:
  - `POST /carfactory` - Creates new cars by accepting brand/color data, requesting a serial number from the serial generator, and storing the car with its assigned serial number
  - `GET /carfactory` - Returns a list of all manufactured cars with their details

- **`examples/carconsumer/main.py`** - A consumer application that demonstrates service orchestration by ordering a Toyota car from the car provider and then retrieving the complete list of manufactured cars. Runs once and exits.

### Step 5: Run the Multi-System Demo

Now you can run the complete multi-system demo in three separate terminal windows.

**Terminal 1 - Start the Serial Generator:**
```bash
source venv/bin/activate
cd examples/serial-number-generator
source serialgenerator.env
python main.py
```

**Terminal 2 - Start the Car Provider:**
```bash
source venv/bin/activate
cd examples/carprovider
source carprovider.env
python main.py
```

**Terminal 3 - Run the Consumer:**
```bash
source venv/bin/activate
cd examples/carconsumer
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

### Step 6: Integration Tests

The file `examples/test.py` contains an integration test for the application that can be run with `pytest`. This test simulates the complete interaction between the three services entirely in-memory, without requiring any authentication, network calls, or a running Arrowhead server. It works by using the SDK's `arrowhead.TestHarness` class, which wires the systems together. When one system tries to send a request to another, the harness intercepts the call and routes it directly to the correct service handler on the provider system.

```
python -m pytest examples/test.py
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
from arrowhead import Request, Response

# Create a request object. The payload will be automatically JSON encoded.
request = Request(payload={"key": "value"})

# Send the request and receive a Response object.
response: Response = await system.send("service-name", request)

# The response content is automatically parsed if it's JSON.
print(response.content) # -> {'result': 'success'}
print(response.status_code) # -> 200
```

**`send` parameters:**
- `service_def`: Service definition name to call
* `request`: An `arrowhead.Request` object containing the payload, query parameters, etc.
* **Returns**: An `arrowhead.Response` object with the parsed response.

### Running Systems

**Start a provider system:**
```python
# Provide a service
@system.service("some-service", method="POST", endpoint="/echo")
async def service(request: Request) -> Response:
    return Response({"message": "Hello, World!"})

# Run system (blocks until stopped)
system.run()
```

**Start a consumer system:**
```python
# Provide a service
@system.main()
async def main():
    response = await system.send("some-service", Request(payload={"data": "hello"}))

system.run()
```

**Start a provider system that is also a consumer:**
```python
@system.service("some-service", method="POST", endpoint="/echo")
async def service(request: Request) -> Response:
    response = await system.send("another-service", Request())
    return Response({"message": f"Hello, World! The other service said: {response.content}"})

system.run()
```

### Complete Example

```python
import json
from arrowhead import System, Request, Response

# Create system
system = System(name="example-system", port=8080, address="localhost")

# Provide a service
@system.service("echo", method="POST", endpoint="/echo")
async def echo_service(request: Request) -> Response:
    return Response({"echo": request.payload["message"]})

# Provide a service with path parameters
@system.service("get-user", method="GET", endpoint="/users/{user_id}")
async def get_user(request: Request) -> Response:
    user_id = request.path_params["user_id"]
    return Response({"user_id": user_id, "name": f"User {user_id}"})

# Start the system
system.run()
```

## Development

### Tooling

This project uses `uv` for dependency management and `ruff` for linting and formatting. It is recommended to use the provided `Makefile` for common development tasks.

### Setup
```bash
# Install uv, create a virtual environment, and sync dependencies
make sync

# To activate the virtual environment manually
source .venv/bin/activate
```

### Running Checks

```bash
# Run all tests with pytest
make test

# Run tests with a coverage report
make test-cov

# Format code with ruff
make format

# Lint code with ruff
make lint

# Run type checks with pyright
make check
```
