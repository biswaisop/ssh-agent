from .file_tools import create_file_tool
from .network_tool import create_network_command
from .process_tool import create_process_command
from .os_tools import create_os_command

all_tools = [create_file_tool, create_network_command, create_process_command, create_os_command]