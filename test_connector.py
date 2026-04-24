# test_connector.py
from connectors.ssh_connector import PersistentSSHConnector

c = PersistentSSHConnector(
    host="localhost",
    username="ubuntu",
    key_path="C:/Users/monda/.ssh/id_rsa"
)

c.connect()
print("Connected:", c.is_connected)

# Test cd context persists
print(c.exec("pwd"))           # /home/ubuntu
print(c.exec("cd /var/log"))   # Done.
print(c.exec("pwd"))           # /var/log  ← context preserved
print(c.exec("ls | head -5"))  # lists /var/log ← correct

# Test multi-command
print(c.exec("mkdir -p /tmp/genos_test && cd /tmp/genos_test && pwd"))

c.disconnect()
print("Disconnected:", c.is_connected)