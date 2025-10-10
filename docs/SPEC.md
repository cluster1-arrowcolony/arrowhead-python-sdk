# Python SDK Specification

## Introduction

This document describes the user-facing API and behavior of the `py-arrowhead` Python SDK and its associated Command-Line Interface (CLI). It serves as a definitive reference for developers building applications and managing resources that interact with the Arrowhead Framework, whether as service providers, consumers, or during end-to-end testing.

The SDK simplifies the development of secure, discoverable, and interoperable systems within the Arrowhead ecosystem by abstracting away the complexities of core system interactions, mTLS security, and HTTP communication.

## Core Principles of the SDK

1.  **System-Centric Design:** The primary entry point for any Arrowhead application is the `System` class, which encapsulates the identity and communication capabilities of a single Arrowhead system.
2.  **Explicit Request/Response Model:** All service interactions use well-defined `Request` and `Response` objects, promoting clarity and consistency.
3.  **Decorator-Based Service Definition:** Providing services is achieved through clear, Pythonic decorators, separating business logic from communication concerns.
4.  **Asynchronous by Design:** The SDK is built on `asyncio` to facilitate non-blocking I/O and efficient handling of concurrent network operations.
5.  **Testability:** A `Simulator` class is provided to enable robust, in-memory end-to-end testing of interacting Arrowhead systems without network overhead.

## 1. The `System` Class

The `System` class is the central component for developing Arrowhead applications. An instance of this class represents an Arrowhead system and can act as both a service provider and a service consumer. It manages network identity, service registration, orchestration requests, and mTLS security.

### 1.1. Constructor: `System.__init__()`

Initializes a new Arrowhead `System` instance. All parameters are optional if corresponding environment variables are set.

```python
class System:
    def __init__(
        self,
        name: Optional[str] = None,
        port: Optional[int] = None,
        address: Optional[str] = None,
        config: Optional[Config] = None
    ): ...
```

*   **`name`** (`str`, optional):
    *   The unique name of the Arrowhead system. If not provided, it defaults to the value of the `ARROWHEAD_SYSTEM_NAME` environment variable.
    *   **Requirement:** Must be provided either as an argument or via the environment variable.
    *   **Error:** Raises `ValueError` if the system name is not provided.
*   **`port`** (`int`, optional):
    *   The network port on which the system will listen for incoming requests. If not provided, it defaults to `8080` or the value of `ARROWHEAD_SYSTEM_PORT` environment variable.
*   **`address`** (`str`, optional):
    *   The network address (hostname or IP) of the system. If not provided, it defaults to `"localhost"` or the value of `ARROWHEAD_SYSTEM_ADDRESS` environment variable.
*   **`config`** (`Optional[Config]`, optional):
    *   An optional `Config` object to explicitly provide Arrowhead Core System addresses and security settings. If `None`, the configuration is loaded from environment variables.

### 1.2. Service Provider Registration: `@system.service` Decorator

Registers a function as an Arrowhead service provider endpoint. The decorated function will be called when an incoming HTTP request matches the defined method and endpoint.

```python
class System:
    def service(self, name: str, method: str, endpoint: str) -> Callable: ...
```

*   **`name`** (`str`):
    *   A unique logical name for the service, used for internal identification and for orchestration (`System.send`).
*   **`method`** (`str`):
    *   The HTTP method (e.g., "GET", "POST", "PUT", "DELETE") that this service handler will respond to. It is converted to uppercase internally.
*   **`endpoint`** (`str`):
    *   The URL path (e.g., `"/my-service/data"`, `"/items/{item_id}"`) where this service will be exposed. Path parameters (e.g., `{item_id}`) are automatically parsed and made available in the `Request` object.
*   **Decorated Function Signature:** `async def handler(request: Request) -> Response: ...`
    *   The handler must be an `async` function.
    *   It receives a `Request` object containing parsed input.
    *   It must return a `Response` object.
*   **Error:** Raises `RuntimeError` if an attempt is made to register new services after the system has already been started (`System.run` or `System.arun`).

### 1.3. Service Consumer Entry Point: `@system.main` Decorator

Registers an asynchronous function as the main entry point for a system that primarily acts as a consumer or orchestrator of other services. This function is executed when `System.arun()` (or `System.run()`) is called if no services have been registered on the system.

```python
class System:
    def main(self) -> Callable: ...
```

*   **Decorated Function Signature:** `async def main_handler() -> None: ...`
    *   The handler must be an `async` function.
    *   It takes no arguments and returns `None`.
*   **Error:** Raises `RuntimeError` if more than one `@system.main()` handler is registered on a single `System` instance.

### 1.4. Requesting Services: `System.send()`

Sends a request to another Arrowhead service. This method handles the entire orchestration process (finding a provider for the `service_name`), secure token exchange, and mTLS communication.

```python
class System:
    async def send(self, service_name: str, request: Request) -> Response: ...
```

*   **`service_name`** (`str`):
    *   The logical name of the service definition to be requested (e.g., "MyService"). This name is used to query the Orchestrator for available providers.
*   **`request`** (`Request`):
    *   A `Request` object containing the payload, query parameters, and headers for the outgoing request.
*   **Returns:** `Response`
    *   A `Response` object representing the received response from the service provider.
*   **Errors:**
    *   Raises `RuntimeError` if the Arrowhead Orchestrator does not find any suitable providers for the requested `service_name`.
    *   Raises `ValueError` if required authorization tokens or HTTP method metadata are missing from the orchestration response.

### 1.5. System Lifecycle: `run()` and `arun()`

Starts the Arrowhead system. This initiates the underlying web server (for service providers) or executes the main consumer function (for consumer systems).

```python
class System:
    def run(self) -> None: ...
    async def arun(self) -> None: ...
    async def aclose(self) -> None: ...
    async def __aenter__(self) -> "System": ...
    async def __aexit__(self, exc_type, exc_val, exc_tb): ...
```

*   **`run()`**:
    *   Synchronous entry point. It internally runs `System.arun()` using `asyncio.run()`.
*   **`arun()`**:
    *   Asynchronous, entry point. This method must be `await`ed. It integrates with an existing `asyncio` event loop. If services are registered, `arun()` starts an mTLS-enabled HTTP server to listen for incoming requests. If a `@system.main()` function is registered, it executes that function. This is preferred for applications that manage multiple concurrent asynchronous tasks.
*   **Error:** Raises `RuntimeError` if both `@system.main()` and `@system.service()` decorators are used on the same `System` instance, as a system cannot simultaneously act as a pure consumer and a provider through these entry points.
*   **Warning:** Logs a warning if neither services are registered nor a main function is defined, indicating that the system has nothing to run.
*   **`aclose()`**: Asynchronously closes the client and cleans up resources.
*   **`__aenter__()` / `__aexit__()`**: The `System` class is an asynchronous context manager, enabling `async with System(...) as system:` usage for proper resource management.

## 2. Request and Response Models

The `Request` and `Response` dataclasses are used for abstracting HTTP communication within the SDK. Service handlers receive `Request` objects and must return `Response` objects.

### 2.1. `Request` Model

Represents an incoming request to a service handler or an outgoing request to another service.

```python
@dataclass
class Request:
    payload: Any = None
    query_params: Dict[str, str] = field(default_factory=dict)
    path_params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    # ... (internal methods)
```

*   **`payload`** (`Any`):
    *   For incoming requests: The request body. Automatically parsed into a `dict` or `list` if `Content-Type` is `application/json`; otherwise, it will be raw `bytes`.
    *   For outgoing requests: The request body to send. Can be `dict`, `list`, `str`, or `bytes`. If the `Content-Type` header is not explicitly provided in `headers`, the SDK automatically sets it as follows: `application/json` for `dict` or `list` payloads, `text/plain` for `str` payloads (or other types implicitly converted to `str`), and `application/octet-stream` for `bytes` payloads.
*   **`query_params`** (`Dict[str, str]`):
    *   A dictionary of URL query parameters (e.g., `?key=value`).
*   **`path_params`** (`Dict[str, Any]`):
    *   A dictionary of URL path parameters (e.g., `{item_id}` from `"/items/{item_id}"`).
*   **`headers`** (`Dict[str, str]`):
    *   A dictionary of request headers.

### 2.2. `Response` Model

Represents an outgoing response from a service handler or an incoming response from another service.

```python
@dataclass
class Response:
    content: Any
    status_code: int = 200
    media_type: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    # ... (internal methods)
```

*   **`content`** (`Any`):
    *   The response body to send. Can be `bytes`, `str`, `dict`, or `list`. For incoming responses, it is automatically parsed from JSON if the `Content-Type` is `application/json`; otherwise, it will be raw `bytes`.
*   **`status_code`** (`int`, default: `200`):
    *   The HTTP status code for the response (e.g., `200` for OK, `404` for Not Found).
*   **`media_type`** (`Optional[str]`, default: `None`):
    *   The MIME type of the response (e.g., `"application/json"`, `"text/plain"`). If `None`, the SDK will attempt to auto-detect based on the `content` type.
*   **`headers`** (`Dict[str, str]`):
    *   A dictionary of response headers.

## 3. Simulator for End-to-End Testing

The `Simulator` class provides an in-memory environment to test interactions between multiple `System` instances without requiring actual network communication or running Arrowhead Core Systems. It allows for simulating network faults and crashes.

### 3.1. Constructor: `Simulator(__init__)`

Initializes a new `Simulator` instance with a list of `System` objects to be tested.

```python
class Simulator:
    def __init__(self, systems: List[System]): ...
```

*   **`systems`** (`List[System]`):
    *   A list of `System` instances that will participate in the simulated environment. The `Simulator` takes control of these systems' communication mechanisms.

### 3.2. Fault Injection Methods

These methods allow for simulating various network and system failures within the testing environment.

*   **`crash(system_name: str) -> None`**:
    *   Simulates a system node crashing. The specified system will no longer respond to requests.
    *   **Error:** Raises `ValueError` if the `system_name` is not part of this simulation.
*   **`recover(system_name: str) -> None`**:
    *   Recovers a previously crashed system, allowing it to respond to requests again.
*   **`disconnect(system_a: str, system_b: str) -> None`**:
    *   Creates a network partition between `system_a` and `system_b`. Communication attempts between these two systems will fail in both directions.
    *   **Error:** Raises `ValueError` if either `system_a` or `system_b` is not part of this simulation.
*   **`reconnect(system_a: str, system_b: str) -> None`**:
    *   Removes a network partition between `system_a` and `system_b`, restoring their connectivity.

### 3.3. Direct Request from Simulator: `send()`

Sends a request to a service from the `Simulator` itself, bypassing the need for a specific `System` instance to initiate the request.

```python
class Simulator:
    async def send(self, service_name: str, request: Request) -> Response: ...
```

*   **`service_name`** (`str`):
    *   The logical name of the service definition to be requested.
*   **`request`** (`Request`):
    *   A `Request` object containing the payload, query parameters, and headers for the outgoing request.
*   **Returns:** `Response`
    *   A `Response` object representing the received response from the service provider.
*   **Errors:**
    *   Raises `RuntimeError` if no provider system is registered for the `service_name` within the simulation.
    *   Raises `httpx.ConnectError` if the targeted provider system has crashed or is part of a simulated network partition.

### 3.4. Context Manager: `__aenter__()` and `__aexit__()`

```python
class Simulator:
    async def __aenter__(self) -> "Simulator": ...
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: ...
```

*   **Behavior on Entry (`__aenter__`)**:
    *   For each `System` passed to the `Simulator`'s constructor, its `send` method is replaced with the `Simulator`'s internal routing logic.
    *   If any `System` has a `@system.main()` function, that function is executed upon entry to allow consumer systems to initiate their tasks.
*   **Behavior on Exit (`__aexit__`)**:
    *   The original `send` methods of all managed `System` instances are restored.
    *   All internal `httpx.AsyncClient` instances used by the simulator are closed.

The `Simulator` class is an asynchronous context manager. Entering the context manager temporarily replaces the `send` method of all managed `System` instances with the simulator's internal routing mechanism, enabling in-memory communication. Exiting the context restores the original `send` methods.

## 4. Environment Variables

This section describes the environment variables used by the SDK and CLI for configuration. These variables allow for externalizing settings such as system identity, network addresses of Arrowhead Core Systems, and security credentials.

### 4.1. General SDK and CLI Configuration

These variables are used by the SDK runtime and general CLI operations.

*   **`ARROWHEAD_VERBOSE`** (`str`, optional): If set to `"1"`, enables verbose logging output for the SDK and CLI.
*   **`ARROWHEAD_KEYSTORE_PATH`** (`str`): Path to the PKCS#12 keystore file for mTLS client authentication for standard SDK systems (consumers/providers). Required for any `System` instance acting as a client to Arrowhead Core Systems.
*   **`ARROWHEAD_SYSOPS_KEYSTORE`** (`str`): Path to the PKCS#12 keystore file used by the CLI for privileged management operations (e.g., registering systems/services, adding authorizations). This keystore is required to contain credentials with elevated permissions.
*   **`ARROWHEAD_KEYSTORE_PASSWORD`** (`str`): Password for the PKCS#12 keystore specified by `ARROWHEAD_KEYSTORE_PATH` or `ARROWHEAD_SYSOPS_KEYSTORE`. Used by both the SDK and CLI.
*   **`ARROWHEAD_TRUSTSTORE`** (`str`): Path to the PEM truststore file containing the CA certificates for validating Arrowhead Core System servers. Used by both the SDK and CLI.

### 4.2. System Instance Configuration

These variables are used by the `System` class constructor if not explicitly provided as arguments.

*   **`ARROWHEAD_SYSTEM_NAME`** (`str`): The unique name of the Arrowhead system.
*   **`ARROWHEAD_SYSTEM_PORT`** (`int`, default: `8080`): The network port on which the system will listen for incoming requests.
*   **`ARROWHEAD_SYSTEM_ADDRESS`** (`str`, default: `"localhost"`): The network address (hostname or IP) of the system.

### 4.3. Arrowhead Core System Addresses

These variables define the network locations of the Arrowhead Core Systems.

*   **`ARROWHEAD_AUTHORIZATION_HOST`** (`str`, default: `"localhost"`): Hostname or IP address of the Authorization Core System.
*   **`ARROWHEAD_AUTHORIZATION_PORT`** (`int`, default: `8443`): Port of the Authorization Core System.
*   **`ARROWHEAD_SERVICEREGISTRY_HOST`** (`str`, default: `"localhost"`): Hostname or IP address of the Service Registry Core System.
*   **`ARROWHEAD_SERVICEREGISTRY_PORT`** (`int`, default: `8443`): Port of the Service Registry Core System.
*   **`ARROWHEAD_ORCHESTRATOR_HOST`** (`str`, default: `"localhost"`): Hostname or IP address of the Orchestrator Core System.
*   **`ARROWHEAD_ORCHESTRATOR_PORT`** (`int`, default: `8443`): Port of the Orchestrator Core System.

### 4.4. Certificate Authority Keystore Configuration (CLI Cert Generation Only)

These variables are specifically used by the `arrowhead certs gen` command for generating system certificates.

*   **`ARROWHEAD_ROOT_KEYSTORE`** (`str`, optional): Path to the root CA PKCS#12 keystore for certificate signing.
*   **`ARROWHEAD_ROOT_KEYSTORE_ALIAS`** (`str`, optional): Alias for the root keystore entry.
*   **`ARROWHEAD_CLOUD_KEYSTORE`** (`str`, optional): Path to the cloud CA PKCS#12 keystore.
*   **`ARROWHEAD_CLOUD_KEYSTORE_ALIAS`** (`str`, optional): Alias for the cloud keystore entry.

## 5. Command-Line Interface (CLI)

The `py-arrowhead` SDK provides a command-line interface (`arrowhead`) for direct interaction with Arrowhead Core Systems. This CLI simplifies common management tasks such as registering systems and services, managing authorization rules, and generating mTLS certificates.

All CLI commands can be run with the `--verbose` or `-v` flag to enable detailed logging output.

### 5.1. `arrowhead version`

Displays the version of the `py-arrowhead` SDK and the Python interpreter.

### 5.2. `arrowhead env`

Shows the current environment configuration parsed by the CLI, detailing the Arrowhead Core System addresses and security settings. This helps in verifying that environment variables are correctly set.

### 5.3. `arrowhead systems`

Group of commands for managing Arrowhead systems registered in the Service Registry.

#### 5.3.1. `arrowhead systems ls [--filter <name>]`

Lists all registered systems.
*   **`--filter`, `-f`** (`str`, optional): Filters the list of systems by name (case-insensitive substring match).

#### 5.3.2. `arrowhead systems get --id <id>`

Retrieves detailed information about a specific system by its ID.
*   **`--id`, `-i`** (`int`, required): The numerical ID of the system.

#### 5.3.3. `arrowhead systems register --name <name> --address <address> --port <port> [--batch] [...]`

Registers one or more Arrowhead systems. This command also generates a PKCS#12 keystore and a public key file (`.pub`) for each registered system, and an environment file (`.env`) with default configurations.

*   **`--name`** (`str`, multiple, required): The unique name of the system. Can be used multiple times for registering multiple systems.
        *   **Requirement:** Must be alphanumeric (letters A-Z, a-z, and digits 0-9).
*   **`--address`** (`str`, multiple, required): The IP address or hostname of the system.
*   **`--port`** (`int`, multiple, required): The network port of the system.
*   **`--batch`** (`boolean`, optional): If set, uses the batch registration API endpoint (`/mgmt/systems/batch`) to register all systems in a single request. By default (without this flag), systems are registered individually using the standard endpoint (`/mgmt/systems`).

**Registration Modes:**
- **Individual Registration (default)**: Each system is registered separately via `POST /serviceregistry/mgmt/systems`. This is compatible with the official Arrowhead Framework.
- **Batch Registration (`--batch` flag)**: All systems are registered in a single request via `POST /serviceregistry/mgmt/systems/batch` for improved performance. This is a non-standard feature not supported by the official Arrowhead Framework.

**Multiple Systems:** When registering multiple systems, `name`, `address`, and `port` options must be provided for each system in corresponding order.

**Certificate Generation:** For each system, this command generates an mTLS PKCS#12 keystore (e.g., `mysystem.p12`) and a public key file (e.g., `mysystem.pub`) using the configured root and cloud keystores (via environment variables, see `arrowhead certs gen`). If a PKCS#12 keystore with the system's name already exists, the generation step is skipped for that system, and the public key is extracted from the existing file. The extracted public key is then used as `authenticationInfo` during system registration.

**Environment File:** A corresponding `.env` file (e.g., `mysystem.env`) is created, containing the environment variables required for that system to operate a `py-arrowhead` application. This file explicitly includes the `ARROWHEAD_KEYSTORE_PASSWORD` in plain text, alongside:
*   `ARROWHEAD_VERBOSE`: Set to `false` by default.
*   `ARROWHEAD_KEYSTORE_PATH`: Specifies the location of the system's mTLS keystore for client authentication.
*   `ARROWHEAD_KEYSTORE_PASSWORD`: The password for the specified keystore.
*   `ARROWHEAD_TRUSTSTORE`: The path to the truststore file, used to validate certificates of Arrowhead Core Systems (defaults to `"truststore.pem"` if not explicitly set in the environment from which `arrowhead systems register` is run).
*   `ARROWHEAD_SYSTEM_NAME`: The unique identifier for this system within the Arrowhead Framework.
*   `ARROWHEAD_SYSTEM_ADDRESS`: The network address (hostname or IP) where this system is accessible.
*   `ARROWHEAD_SYSTEM_PORT`: The network port where this system listens for incoming requests.
*   `ARROWHEAD_AUTHORIZATION_HOST`, `ARROWHEAD_AUTHORIZATION_PORT`: The address and port for the Authorization Core System.
*   `ARROWHEAD_SERVICEREGISTRY_HOST`, `ARROWHEAD_SERVICEREGISTRY_PORT`: The address and port for the Service Registry Core System.
*   `ARROWHEAD_ORCHESTRATOR_HOST`, `ARROWHEAD_ORCHESTRATOR_PORT`: The address and port for the Orchestrator Core System.

#### 5.3.4. `arrowhead systems unregister --id <id>`

Unregisters a system from the Service Registry by its ID.
*   **`--id`, `-i`** (`int`, required): The numerical ID of the system to unregister.

### 5.4. `arrowhead services`

Group of commands for managing Arrowhead services registered in the Service Registry.

#### 5.4.1. `arrowhead services ls`

Lists all registered services.

#### 5.4.2. `arrowhead services get --id <id> [--authinfo]`

Retrieves detailed information about a specific service by its ID.
*   **`--id`, `-i`** (`int`, required): The numerical ID of the service.
*   **`--authinfo`** (`boolean`, optional): If set, includes the provider system's authentication information (public key) in the output.

#### 5.4.3. `arrowhead services register --system <name> --definition <name> --uri <path> --method <method> [--batch] [...]`

Registers one or more services. Services require an existing provider system to be registered first.

*   **`--system`** (`str`, multiple, required): The name of the provider system for the service.
*   **`--definition`** (`str`, multiple, required): The logical service definition name (e.g., "TemperatureService").
*   **`--uri`** (`str`, multiple, required): The URI path where the service is exposed (e.g., `/temperature`).
*   **`--method`** (`str`, multiple, required): The HTTP method the service responds to (e.g., `GET`, `POST`, `PUT`, `DELETE`).
*   **`--batch`** (`boolean`, optional): If set, uses the batch registration API endpoint (`/mgmt/services/batch`) to register all services in a single request. By default (without this flag), services are registered individually using the standard endpoint (`/mgmt/services`).

**Registration Modes:**
- **Individual Registration (default)**: Each service is registered separately via `POST /serviceregistry/mgmt/services`. This is compatible with the official Arrowhead Framework.
- **Batch Registration (`--batch` flag)**: All services are registered in a single request via `POST /serviceregistry/mgmt/services/batch` for improved performance. This is a non-standard feature not supported by the official Arrowhead Framework.

**Multiple Services:** Similar to `systems register`, multiple service parameters must be provided in corresponding order when registering multiple services.

#### 5.4.4. `arrowhead services unregister --id <id>`

Unregisters a service from the Service Registry by its ID.
*   **`--id`, `-i`** (`int`, required): The numerical ID of the service to unregister.

### 5.5. `arrowhead auths`

Group of commands for managing authorization rules in the Authorization Core System.

#### 5.5.1. `arrowhead auths ls`

Lists all registered authorization rules.

#### 5.5.2. `arrowhead auths add --consumer <name> --provider <name> --service <definition> [--batch] [...]`

Adds one or more authorization rules. An authorization rule grants a `consumer` system access to a specific `service` provided by a `provider` system. All referenced systems and services must already be registered.

*   **`--consumer`** (`str`, multiple, required): The name of the consumer system.
*   **`--provider`** (`str`, multiple, required): The name of the provider system.
*   **`--service`** (`str`, multiple, required): The service definition name.
*   **`--batch`** (`boolean`, optional): If set, uses the batch authorization API endpoint (`/mgmt/intracloud/batch`) to add all authorization rules in a single request. By default (without this flag), rules are added individually using the standard endpoint (`/mgmt/intracloud`).

**Authorization Modes:**
- **Individual Authorization (default)**: Each authorization rule is added separately via `POST /authorization/mgmt/intracloud`. This is compatible with the official Arrowhead Framework.
- **Batch Authorization (`--batch` flag)**: All authorization rules are added in a single request via `POST /authorization/mgmt/intracloud/batch` for improved performance. This is a non-standard feature not supported by the official Arrowhead Framework.

**Multiple Rules:** Multiple authorization rules can be added by providing corresponding `consumer`, `provider`, and `service` options. The CLI automatically resolves system and service IDs and finds associated interfaces.

#### 5.5.3. `arrowhead auths remove --id <id>`

Removes an authorization rule by its ID.
*   **`--id`, `-i`** (`int`, required): The numerical ID of the authorization rule to remove.

### 5.6. `arrowhead certs`

Group of commands for managing mTLS certificates.

#### 5.6.1. `arrowhead certs gen --name <name> [--root-keystore <path>] [...]`

Generates an mTLS PKCS#12 certificate and private key for a new Arrowhead system. This command requires the path and alias for a root CA and a cloud CA keystore. The generated certificate includes the system's Subject Alternative Name (SAN) and is signed by the cloud CA, which is ultimately trusted by the root CA.

*   **`--name`, `-n`** (`str`, required): The unique name of the system for which to generate the certificate. This name is used as the Common Name (CN) in the certificate's subject and also included in the Subject Alternative Name (SAN). The Common Name (CN) for the certificate subject will be `CN=<name>`.
*   **`--root-keystore`** (`str`, optional): Path to the root CA's PKCS#12 keystore. Defaults to `ARROWHEAD_ROOT_KEYSTORE` environment variable.
*   **`--root-alias`** (`str`, optional): Alias for the root CA's entry in its keystore. Defaults to `ARROWHEAD_ROOT_KEYSTORE_ALIAS` environment variable.
*   **`--cloud-keystore`** (`str`, optional): Path to the cloud CA's PKCS#12 keystore. Defaults to `ARROWHEAD_CLOUD_KEYSTORE` environment variable.
*   **`--cloud-alias`** (`str`, optional): Alias for the cloud CA's entry in its keystore. Defaults to `ARROWHEAD_CLOUD_KEYSTORE_ALIAS` environment variable.
*   **`--password`** (`str`, optional): The password for all keystores involved in the generation process. Defaults to `ARROWHEAD_KEYSTORE_PASSWORD` environment variable or prompts if not set.

**Output:**
-   `<name>.p12`: The generated system PKCS#12 keystore.
-   `<name>.pub`: The extracted public key in PEM format, suitable for `authenticationInfo` in system registration.
-   `<name>.env`: An environment file with relevant `ARROWHEAD_` variables pre-filled for the newly created system. This includes `ARROWHEAD_VERBOSE` set to `false` and `ARROWHEAD_TRUSTSTORE` defaulting to `"truststore.pem"` if not explicitly set. This includes `ARROWHEAD_VERBOSE` set to `false` and `ARROWHEAD_TRUSTSTORE` defaulting to `"truststore.pem"` if not explicitly set.

#### 5.6.2. `arrowhead certs convert --p12-file <path> [--password <pass>] [--cert-output <path>] [--key-output <path>]`

Converts a PKCS#12 keystore file into separate PEM-encoded certificate and private key files. This is useful for tools that require PEM format.

*   **`--p12-file`** (`str`, required): Path to the input PKCS#12 file.
*   **`--password`** (`str`, optional): Password for the PKCS#12 file. Defaults to `ARROWHEAD_KEYSTORE_PASSWORD` environment variable or "changeit".
*   **`--cert-output`** (`str`, optional): Path for the output PEM certificate file. Defaults to `<p12-file-basename>.crt`.
*   **`--key-output`** (`str`, optional): Path for the output PEM private key file. Defaults to `<p12-file-basename>.key`.

### 5.7. `arrowhead orchestrate --service <definition> [--system <name>] [...]`

Requests service orchestration from the Orchestrator Core System. This command simulates a `py-arrowhead` system requesting a service and returns the details of matched providers.

*   **`--service`** (`str`, required): The service definition name to orchestrate for.
*   **`--system`** (`str`, optional): The name of the requester system. Defaults to `ARROWHEAD_SYSTEM_NAME` or "cli-consumer".
*   **`--address`** (`str`, optional): The address of the requester system. Defaults to `ARROWHEAD_SYSTEM_ADDRESS` or "localhost".
*   **`--port`** (`int`, optional): The port of the requester system. Defaults to `ARROWHEAD_SYSTEM_PORT` or `8080`.
*   **`--keystore`** (`str`, optional): Path to the requester's PKCS#12 keystore. Overrides `ARROWHEAD_KEYSTORE_PATH`.
*   **`--password`** (`str`, optional): Password for the requester's keystore. Overrides `ARROWHEAD_KEYSTORE_PASSWORD`.
*   **`--compact`** (`boolean`, optional): If set, displays a compact output table with only provider name, address, and URI.
