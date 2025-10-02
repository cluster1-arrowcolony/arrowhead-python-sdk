# Arrowhead Python SDK API Reference

This document describes the complete API available to applications using the arrowhead-python-sdk.

## Table of Contents
- [High-Level Decorator API](#high-level-decorator-api)
- [Framework API](#framework-api)
- [Service API](#service-api)
- [Data Models](#data-models)
- [RPC Client API](#rpc-client-api)
- [Configuration](#configuration)

## High-Level Decorator API

### `@system` Decorator

Marks a class as an Arrowhead system. Systems are the basic units that provide and consume services.

```python
from arrowhead import system

@system("system-name")  # Optional: specify custom name
class MySystem:
    def __init__(self):
        # REQUIRED: Each instance must have a unique key
        self.key = "unique-identifier"
```

**Parameters:**
- `cls_or_name` (Optional[Union[Type, str]]): System name or class. If not provided, converts class name to kebab-case.

**System Naming:**
- Final system name format: `{base-name}-{key}`
- Example: `temperature-monitor-sensor-01`

### `@service` Decorator

Marks a method as an Arrowhead service within a system.

```python
from arrowhead import service

@service  # Auto-detects method and generates name
def get_data(self):
    return {"data": "value"}

@service("custom-name", method="POST")  # Custom name and method
def process_data(self, payload):
    return {"result": "processed"}
```

**Parameters:**
- `func_or_name` (Optional[Union[Callable, str]]): Service name or function
- `method` (Optional[Union[str, HTTPMethod]]): HTTP method (GET, POST, PUT, DELETE). Auto-detected if not provided.
- `endpoint` (Optional[str]): Custom endpoint path. Auto-generated if not provided.

**Method Auto-Detection:**
- GET: If function has no payload/data/body parameters
- POST: If function has payload/data/body parameters

### ArrowheadProvider Base Class

Base class automatically inherited when using `@system` decorator.

**Methods:**

#### `start()`
Starts the Arrowhead provider, registers services, and begins serving requests.

```python
system = MySystem()
system.start()  # Blocks until stopped
```

#### `stop()`
Stops the provider and cleans up resources.

```python
system.stop()
```

#### `send_request(service_definition, payload=None, query_params=None)`
Send a request to another Arrowhead service (for provider-to-provider communication).

```python
response = self.send_request(
    "other-service",
    payload={"data": "value"},
    query_params={"param": "value"}
)
```

**Parameters:**
- `service_definition` (str): Name of the service to call
- `payload` (Optional[Dict[str, Any]]): Request payload
- `query_params` (Optional[Dict[str, str]]): Query parameters

**Returns:** Dict[str, Any] - Response from the service

## Framework API

### Framework Class

Core engine for Arrowhead applications.

#### `create_framework()` (Class Method)
Creates and configures a Framework instance from environment variables.

```python
from arrowhead import Framework

framework = Framework.create_framework()
```

**Returns:** Framework instance configured from environment

#### `handle_service(service, http_method, service_definition, service_uri)`
Registers a service handler with the framework.

**Parameters:**
- `service` (Service): Service implementation
- `http_method` (HTTPMethod): HTTP method for the service
- `service_definition` (str): Service name
- `service_uri` (str): Service endpoint path

#### `send_request(service_def, params=None)`
Sends a request to a service via orchestration.

```python
from arrowhead import Params

params = Params(
    query_params={"key": "value"},
    payload=b'{"data": "value"}'
)
response = framework.send_request("service-name", params)
```

**Parameters:**
- `service_def` (str): Service definition name
- `params` (Optional[Params]): Request parameters

**Returns:** bytes - Response data

#### `serve_forever()`
Starts the Flask server and blocks.

```python
framework.serve_forever()
```

#### `start_server()`
Starts the server in a background thread.

```python
framework.start_server()
```

#### `close()`
Cleans up framework resources.

```python
framework.close()
```

## Service API

### Params Class

Container for service request parameters.

```python
from arrowhead import Params

# Create with data
params = Params(
    query_params={"key": "value"},
    payload=b'{"data": "json"}'
)

# Create empty
params = Params.empty()
```

**Attributes:**
- `query_params` (Dict[str, str]): URL query parameters
- `payload` (Optional[bytes]): Request body data

### Service Abstract Base Class

Base class for custom service implementations.

```python
from arrowhead import Service, Params

class MyService(Service):
    def handle_request(self, params: Params) -> bytes:
        # Process request
        return b'{"response": "data"}'
```

**Methods:**
- `handle_request(params: Params) -> bytes`: Abstract method to handle requests

## Data Models

All models use Pydantic for validation and serialization.

### System Models

#### `System`
Represents an Arrowhead system.

**Attributes:**
- `id` (int): System ID
- `system_name` (str): System name
- `address` (str): System address
- `port` (int): System port
- `authentication_info` (Optional[str]): Authentication information
- `metadata` (Optional[Dict[str, str]]): System metadata

#### `SystemRegistration`
Request model for system registration.

**Attributes:**
- `system_name` (str): System name
- `address` (str): System address
- `port` (int): System port
- `authentication_info` (str): Authentication info
- `metadata` (Dict[str, str]): System metadata

### Service Models

#### `Service`
Represents a registered service.

**Attributes:**
- `id` (int): Service ID
- `service_definition` (ServiceDefinition): Service definition
- `provider` (Provider): Service provider
- `service_uri` (str): Service endpoint
- `secure` (str): Security type
- `version` (int): Service version
- `interfaces` (List[Interface]): Supported interfaces
- `metadata` (Optional[Dict[str, str]]): Service metadata

#### `ServiceRegistrationRequest`
Request model for service registration.

**Attributes:**
- `service_definition` (str): Service name
- `provider_system` (ProviderSystem): Provider information
- `service_uri` (str): Service endpoint
- `interfaces` (List[str]): Supported interfaces
- `secure` (str): Security type
- `metadata` (Dict[str, str]): Service metadata

### Orchestration Models

#### `OrchestrationRequest`
Request for service orchestration.

**Attributes:**
- `requester_system` (RequesterSystem): Requesting system
- `requested_service` (RequestedService): Service requirements
- `orchestration_flags` (OrchestrationFlags): Orchestration options
- `preferred_providers` (List[PreferredProvider]): Preferred providers

#### `OrchestrationResponse`
Response from orchestration.

**Attributes:**
- `response` (List[MatchedService]): Matched services

#### `MatchedService`
Service matched by orchestration.

**Attributes:**
- `provider` (Provider): Service provider
- `service_definition` (ServiceDefinition): Service definition
- `service_uri` (str): Service endpoint
- `secure` (str): Security type
- `metadata` (Dict[str, str]): Service metadata
- `authorization_tokens` (Dict[str, str]): Access tokens
- `interfaces` (List[Interface]): Supported interfaces
- `version` (int): Service version

## RPC Client API

### ArrowheadClient Class

Low-level client for Arrowhead core service communication.

#### `__init__(config: Config)`
Initialize client with configuration.

```python
from arrowhead.rpc import ArrowheadClient, Config

config = Config(
    tls=True,
    keystore_path="./system.p12",
    password="123456"
)
client = ArrowheadClient(config)
```

#### Core Service Methods

##### `register_system(system_reg: SystemRegistration) -> System`
Register a system with the service registry.

##### `unregister_system(system: System)`
Unregister a system from the service registry.

##### `register_service(system, http_method, service_definition, service_uri) -> Service`
Register a service with the service registry.

##### `unregister_service(system_name, service_uri, service_definition, address, port)`
Unregister a service from the service registry.

##### `orchestrate(orchestration_req: OrchestrationRequest) -> OrchestrationResponse`
Request service orchestration.

##### `send_request(matched_service, query_params=None, payload=None) -> bytes`
Send request to a matched service.

**Parameters:**
- `matched_service` (MatchedService): Service from orchestration
- `query_params` (Optional[Dict[str, str]]): URL parameters
- `payload` (Optional[bytes]): Request body

**Returns:** bytes - Response data

#### `close()`
Close client and clean up resources.

## Configuration

### Config Class

Configuration for Arrowhead RPC client.

```python
from arrowhead.rpc import Config

config = Config(
    tls=True,
    authorization_host="c1-authorization",
    authorization_port=8445,
    service_registry_host="c1-serviceregistry",
    service_registry_port=8443,
    orchestrator_host="c1-orchestrator",
    orchestrator_port=8441,
    keystore_path="./system.p12",
    truststore_path="./truststore.pem",
    password="123456",
    verify_ssl=True
)
```

**Attributes:**
- `tls` (bool): Enable TLS (default: True)
- `authorization_host` (str): Authorization service host
- `authorization_port` (int): Authorization service port
- `service_registry_host` (str): Service Registry host
- `service_registry_port` (int): Service Registry port
- `orchestrator_host` (str): Orchestrator host
- `orchestrator_port` (int): Orchestrator port
- `keystore_path` (Optional[str]): PKCS#12 certificate path
- `truststore_path` (Optional[str]): CA certificate path
- `password` (Optional[str]): Keystore password
- `verify_ssl` (bool): Verify SSL certificates (default: True)

### HTTPMethod Enum

HTTP methods for service registration.

```python
from arrowhead.rpc import HTTPMethod

HTTPMethod.GET     # 0
HTTPMethod.POST    # 1
HTTPMethod.PUT     # 2
HTTPMethod.DELETE  # 3
```

## Environment Variables

The SDK uses these environment variables for configuration:

```bash
# System identification
ARROWHEAD_SYSTEM_NAME=my-system
ARROWHEAD_SYSTEM_ADDRESS=localhost
ARROWHEAD_SYSTEM_PORT=8080

# Core services
ARROWHEAD_SERVICEREGISTRY_HOST=c1-serviceregistry
ARROWHEAD_SERVICEREGISTRY_PORT=8443
ARROWHEAD_ORCHESTRATOR_HOST=c1-orchestrator
ARROWHEAD_ORCHESTRATOR_PORT=8441
ARROWHEAD_AUTHORIZATION_HOST=c1-authorization
ARROWHEAD_AUTHORIZATION_PORT=8445

# Security
ARROWHEAD_TLS=true
ARROWHEAD_KEYSTORE_PATH=./system.p12
ARROWHEAD_KEYSTORE_PASSWORD=123456
ARROWHEAD_TRUSTSTORE=./truststore.pem

# Logging
ARROWHEAD_VERBOSE=true
```

## Example Usage

### Provider Example

```python
from arrowhead import system, service

@system("temperature-monitor")
class TemperatureSystem:
    def __init__(self):
        self.key = "sensor-01"  # Required unique key

    @service  # GET method auto-detected
    def get_temperature(self):
        return {"temperature": 23.5, "unit": "celsius"}

    @service("set-config", method="POST")
    def configure(self, payload):
        interval = payload.get("interval", 60)
        return {"status": "configured", "interval": interval}

# Start the system
if __name__ == "__main__":
    sensor = TemperatureSystem()
    sensor.start()  # Registers and serves
```

### Consumer Example

```python
from arrowhead import Framework, Params
import json

# Create framework
framework = Framework.create_framework()

# GET request
response = framework.send_request("get-temperature")
print(json.loads(response))

# POST request
params = Params(
    query_params={},
    payload=json.dumps({"interval": 30}).encode()
)
response = framework.send_request("set-config", params)
print(json.loads(response))

# Cleanup
framework.close()
```

### Service Handler Parameter Mapping

The decorator API automatically maps function parameters to request data:

```python
@service
def handler(self, payload):         # Receives parsed JSON payload
    pass

@service
def handler(self, query_params):    # Receives query parameters
    pass

@service
def handler(self, params):          # Receives full Params object
    pass

@service
def handler(self, data):           # Alias for payload
    pass

@service
def handler(self, body):           # Alias for payload
    pass
```

## Error Handling

The SDK raises standard Python exceptions:

- `ValueError`: Invalid configuration or parameters
- `RuntimeError`: Operation failures (registration, orchestration, etc.)
- `requests.RequestException`: Network communication errors

All service handler exceptions are caught and returned as error responses:
```json
{"error": "error message"}
```