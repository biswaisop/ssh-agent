import paramiko
import os
import time

def run_command_ssh(host: str, port: int, username: str, key_path: str, command: str, password: str = None) -> dict:
    """
    Executes a command on a remote machine via SSH using key-based or password-based authentication.
    Includes a timeout to prevent hanging on interactive commands.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 10,
            "allow_agent": True,
            "look_for_keys": True
        }

        if key_path and os.path.exists(key_path):
            connect_kwargs["key_filename"] = key_path
        
        if password:
            connect_kwargs["password"] = password

        ssh.connect(**connect_kwargs)

        # Use a transport-level timeout for the command execution
        transport = ssh.get_transport()
        chan = transport.open_session()
        chan.settimeout(30) # 30 second timeout for the command to finish or produce output
        
        chan.exec_command(command)

        # Buffers for output
        stdout_data = []
        stderr_data = []
        
        # Read loop with timeout
        start_time = time.time()
        while not chan.exit_status_ready():
            if chan.recv_ready():
                stdout_data.append(chan.recv(4096).decode(errors="ignore"))
            if chan.recv_stderr_ready():
                stderr_data.append(chan.recv_stderr(4096).decode(errors="ignore"))
            
            # If we've been waiting too long without the command finishing
            if time.time() - start_time > 25:
                stderr_data.append("\n[ERROR: Command timed out after 25 seconds. It might be waiting for interactive input.]")
                break
            
            time.sleep(0.1)

        # Final check for remaining data
        while chan.recv_ready():
            stdout_data.append(chan.recv(4096).decode(errors="ignore"))
        while chan.recv_stderr_ready():
            stderr_data.append(chan.recv_stderr(4096).decode(errors="ignore"))

        exit_code = chan.recv_exit_status() if chan.exit_status_ready() else -1

        return {
            "stdout": "".join(stdout_data),
            "stderr": "".join(stderr_data),
            "exit_code": exit_code,
            "error": "TIMEOUT" if exit_code == -1 else None
        }

    except paramiko.AuthenticationException:
        return {
            "stdout": "",
            "stderr": "Authentication failed. Please check your SSH keys or password.",
            "exit_code": 1,
            "error": "AUTH_FAILED"
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"SSH Connection Error: {str(e)}",
            "exit_code": 1,
            "error": str(type(e).__name__)
        }
    finally:
        ssh.close()