# Python SDK for the Arrowhead Framework

This is a Python port of the Go SDK and CLI tool for the [Arrowhead Framework](https://arrowhead.eu), an Industrial IoT platform for service-oriented architecture.

## Features

- **Simple Decorator API**: Use `@system` and `@service` decorators for rapid development
- **CLI Tool**: Command-line interface for managing Arrowhead systems, services, and authorizations
- **Automatic Registration**: Services are registered automatically with proper naming
- **TLS Support**: Full mutual TLS authentication using PKCS#12 certificates
- **JSON Handling**: Automatic JSON parsing and response formatting
- **Method Detection**: Auto-detects HTTP methods based on function signatures
- **Remote Deployment**: Works with both local and remote Arrowhead deployments

## Installation

```bash
git clone https://git.ri.se/eu-cop-pilot/arrowhead-python-sdk
cd arrowhead-python-sdk
pip install -e .
```

## Quick Start

### Using the CLI

```bash
# Show environment configuration
arrowhead env

# List registered systems
arrowhead systems ls

# Register a new system
arrowhead systems register --name mysystem --address localhost --port 8080

# List services
arrowhead services ls

# Add authorization rule
arrowhead auths add --consumer consumer-system --provider provider-system --service my-service

# Request orchestration
arrowhead orchestrate --service my-service
```

### Using the SDK

The Python SDK uses a high-level decorator-based API for rapid development. Services are registered automatically using decorators.

#### How to Implement an Arrowhead System

```python
from arrowhead import system, service

@system("temperature-monitor")  # System name in Arrowhead
class TemperatureSystem:
    def __init__(self):
        # Each system instance MUST have a unique key for identification
        self.key = "sensor-01"  # e.g., "sensor-01", "sensor-02", etc.
    
    @service  # Auto-detects GET method (no payload)
    def get_temperature(self):
        return {"temperature": 23.5, "unit": "celsius"}
    
    @service("set-config", method="POST")  # Custom service name
    def configure_sensor(self, payload):
        # JSON payload is automatically parsed
        interval = payload.get("interval", 60)
        return {"status": "configured", "interval": interval}

# Start the system
if __name__ == "__main__":
    sensor = TemperatureSystem()
    sensor.start()  # Registers services and starts server
```

#### How to Send Requests to Other Systems

```python
from arrowhead import Framework

# Create framework for sending requests
framework = Framework.create_framework()

# Send GET request
response = framework.send_request("get-temperature")
print(response.decode('utf-8'))  # {"temperature": 23.5, "unit": "celsius"}

# Send POST request with payload
from arrowhead import Params
params = Params(
    query_params={},
    payload='{"interval": 30}'.encode('utf-8')
)
response = framework.send_request("set-config", params)
print(response.decode('utf-8'))  # {"status": "configured", "interval": 30}
```

**Key Requirements:**
- Each system instance must have a unique `key` attribute that identifies the system
- The final system name becomes `{system-name}-{key}` (e.g., `temperature-monitor-sensor-01`)
- Service names are auto-generated from method names or can be customized

## Configuration

The framework uses environment variables for configuration:

```bash
# System identification
ARROWHEAD_SYSTEM_NAME=my-system
ARROWHEAD_SYSTEM_ADDRESS=localhost
ARROWHEAD_SYSTEM_PORT=8080

# Core service endpoints
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

### Remote Arrowhead Deployment

To connect to a remote Arrowhead deployment, configure the core service hostnames in your environment:

```bash
# For remote deployment at IP 130.237.202.108 with /etc/hosts entries:
# 130.237.202.108 c1-serviceregistry
# 130.237.202.108 c1-orchestrator  
# 130.237.202.108 c1-authorization

export ARROWHEAD_SERVICEREGISTRY_HOST=c1-serviceregistry
export ARROWHEAD_ORCHESTRATOR_HOST=c1-orchestrator
export ARROWHEAD_AUTHORIZATION_HOST=c1-authorization
```

**Important Notes for Remote Deployment:**

1. **Certificate Requirements**: Ensure your PKCS#12 certificates are valid for the remote deployment
2. **System Name Matching**: The system name must match the certificate Common Name (CN)
3. **CLI Management Access**: Use `sysop.p12` certificate for CLI management commands:
   ```bash
   export ARROWHEAD_KEYSTORE_PATH=./sysop.p12
   export ARROWHEAD_KEYSTORE_PASSWORD=123456
   arrowhead systems ls
   ```
4. **Network Connectivity**: Verify that the hostnames resolve correctly in your `/etc/hosts` file

## Examples

Complete examples are provided in the `examples/` directory:

- **Provider**: Car factory service that creates and lists cars
- **Consumer**: Client that consumes the car factory services

### Running the Examples

1. **Set up environment** (provider terminal):
   ```bash
   cd examples/provider
   source carprovider.env
   python provider.py
   ```

2. **Run consumer** (consumer terminal):
   ```bash
   cd examples/consumer
   source carconsumer.env
   python consumer.py
   ```

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
