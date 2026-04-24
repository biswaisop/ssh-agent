import os
from connectors.ssh_connector import PersistentSSHConnector

_connections: dict[str, PersistentSSHConnector] = {}

def get_connector(hostname: str, username: str) -> PersistentSSHConnector:
    connection_id = f"{username}@{hostname}"
    existing = _connections.get(connection_id)

    if existing and existing.is_connected:
        return existing

    connector = PersistentSSHConnector(
        host     = hostname,
        port     = int(os.environ.get("SSH_PORT", 2222)),
        username = username,
        password = os.environ.get("SSH_PASSWORD"),
        key_path = os.environ.get("KEY_PATH"),
    )
    connector.connect()
    _connections[connection_id] = connector
    return connector

def disconnect_user(hostname: str, username: str):
    connection_id = f"{username}@{hostname}"
    connector = _connections.pop(connection_id, None)
    if connector:
        connector.disconnect()