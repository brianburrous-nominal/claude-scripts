"""Log message generator that sends random log messages to a Nominal dataset every second."""

import random
import time
from datetime import datetime

from nominal.core import NominalClient

# ---- Configuration ----
DATASET_RID = "ri.catalog.cerulean-staging.dataset.61aa6048-4ae6-4e4b-8a34-40df8b112fab"
PROFILE_NAME = "default"
CHANNEL_NAME = "logs"

# ---- Log message templates ----
LOG_LEVELS = ["INFO", "DEBUG", "WARN", "ERROR"]
LOG_LEVEL_WEIGHTS = [50, 25, 15, 10]

COMPONENTS = [
    "auth-service",
    "api-gateway",
    "data-pipeline",
    "scheduler",
    "cache-manager",
    "storage-engine",
    "notification-service",
    "metrics-collector",
]

INFO_MESSAGES = [
    "Request processed successfully",
    "Health check passed",
    "Connection pool refreshed",
    "Cache hit for key {key}",
    "User {user_id} authenticated",
    "Batch job completed: {count} records processed",
    "Configuration reloaded",
    "Heartbeat received from node {node_id}",
    "Service started on port {port}",
    "Scheduled task executed",
]

DEBUG_MESSAGES = [
    "Entering function {func_name}",
    "Query executed in {duration_ms}ms",
    "Payload size: {size_bytes} bytes",
    "Retry attempt {attempt} of {max_retries}",
    "Thread pool utilization: {pct}%",
    "Allocated {mem_mb}MB of memory",
    "DNS resolution for {host} took {dns_ms}ms",
]

WARN_MESSAGES = [
    "Response time exceeded threshold: {duration_ms}ms",
    "Disk usage at {pct}% capacity",
    "Rate limit approaching for client {client_id}",
    "Deprecated API version used by {caller}",
    "Connection pool nearing capacity: {used}/{max}",
    "Certificate expires in {days} days",
    "Memory usage above 80%: {mem_mb}MB",
]

ERROR_MESSAGES = [
    "Failed to connect to database: timeout after {duration_ms}ms",
    "Unhandled exception in request handler: {error}",
    "Authentication failed for user {user_id}",
    "Circuit breaker tripped for {service}",
    "Write operation failed: disk full",
    "TLS handshake failed with {host}",
    "Message queue backlog exceeded {count} messages",
]

MESSAGES_BY_LEVEL = {
    "INFO": INFO_MESSAGES,
    "DEBUG": DEBUG_MESSAGES,
    "WARN": WARN_MESSAGES,
    "ERROR": ERROR_MESSAGES,
}

PLACEHOLDER_VALUES = {
    "key": lambda: f"user:{random.randint(1000, 9999)}",
    "user_id": lambda: f"usr_{random.randint(10000, 99999)}",
    "count": lambda: str(random.randint(10, 10000)),
    "node_id": lambda: f"node-{random.randint(1, 20)}",
    "port": lambda: str(random.choice([8080, 8443, 3000, 5000, 9090])),
    "func_name": lambda: random.choice(["handle_request", "process_event", "validate_input", "serialize_output"]),
    "duration_ms": lambda: str(random.randint(1, 5000)),
    "size_bytes": lambda: str(random.randint(64, 1048576)),
    "attempt": lambda: str(random.randint(1, 5)),
    "max_retries": lambda: "5",
    "pct": lambda: str(random.randint(50, 99)),
    "mem_mb": lambda: str(random.randint(256, 4096)),
    "host": lambda: random.choice(["db-primary.internal", "cache-01.internal", "api.example.com"]),
    "dns_ms": lambda: str(random.randint(1, 200)),
    "client_id": lambda: f"client-{random.randint(100, 999)}",
    "caller": lambda: f"service-{random.choice(['alpha', 'beta', 'gamma'])}",
    "used": lambda: str(random.randint(80, 95)),
    "max": lambda: "100",
    "days": lambda: str(random.randint(1, 30)),
    "error": lambda: random.choice(["NullPointerError", "TimeoutError", "ValueError", "ConnectionResetError"]),
    "service": lambda: random.choice(["payment-api", "user-service", "inventory-service"]),
}


def fill_placeholders(template: str) -> str:
    """Replace {placeholder} tokens with random values."""
    result = template
    for key, gen in PLACEHOLDER_VALUES.items():
        token = "{" + key + "}"
        if token in result:
            result = result.replace(token, gen())
    return result


def generate_log_message() -> tuple[str, str, dict[str, str]]:
    """Generate a random log level, message, and args dict."""
    level = random.choices(LOG_LEVELS, weights=LOG_LEVEL_WEIGHTS, k=1)[0]
    component = random.choice(COMPONENTS)
    template = random.choice(MESSAGES_BY_LEVEL[level])
    message = fill_placeholders(template)

    return (
        f"[{level}] [{component}] {message}",
        level,
        {"level": level, "component": component},
    )


def main() -> None:
    print(f"Connecting to Nominal using profile '{PROFILE_NAME}'...")
    client = NominalClient.from_profile(PROFILE_NAME)

    print(f"Fetching dataset {DATASET_RID}...")
    dataset = client.get_dataset(DATASET_RID)

    print(f"Streaming log messages to channel '{CHANNEL_NAME}' (Ctrl+C to stop)")
    print("-" * 60)

    with dataset.get_log_stream() as stream:
        count = 0
        try:
            while True:
                message, _level, _args = generate_log_message()
                now = datetime.now()
                stream.enqueue(
                    channel_name=CHANNEL_NAME,
                    timestamp=now,
                    value=message,
                )
                count += 1
                print(f"[{now.isoformat()}] #{count}: {message}")
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\nStopping. Sent {count} log messages.")


if __name__ == "__main__":
    main()
