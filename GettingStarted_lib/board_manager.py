import yaml
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

@dataclass
class BoardConfig:
    name: str
    ip: str
    linien_port: int
    ssh_port: int = 22
    username: Optional[str] = None
    password: Optional[str] = None

    def validate(self):
        """Validates the board configuration."""
        if not self.name or not isinstance(self.name, str):
            raise ValueError(f"Invalid board name: {self.name}")
        
        # Simple IP validation
        ip_pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
        if not re.match(ip_pattern, self.ip) and self.ip != "localhost":
            # Basic check, might be a hostname too, but user asked for robust checks
            if not self.ip:
                raise ValueError(f"IP address cannot be empty for board {self.name}")

        if not (1 <= self.linien_port <= 65535):
            raise ValueError(f"Invalid Linien port: {self.linien_port}")
        
        if not (1 <= self.ssh_port <= 65535):
            raise ValueError(f"Invalid SSH port: {self.ssh_port}")

class BoardManager():
    DEFAULT_CONFIG_PATH = Path(__file__).parent / "boards/board_list.yaml" #"connect_config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self.boards: Dict[str, BoardConfig] = {}
        self.global_username: Optional[str] = None
        self.global_password: Optional[str] = None
        self.load()

    def load(self):
        """Loads configuration from YAML."""
        if not self.config_path.exists():
            return

        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f) or {}

        self.global_username = data.get("username")
        self.global_password = data.get("password")
        
        devices = data.get("devices", [])
        self.boards = {}
        for dev in devices:
            board = BoardConfig(
                name=dev["name"],
                ip=dev["ip"],
                linien_port=dev["linien_port"],
                ssh_port=dev.get("ssh_port", 22),
                username=dev.get("username"),
                password=dev.get("password")
            )
            board.validate()
            self.boards[board.name] = board

    def save(self):
        """Saves current configuration to YAML."""
        data = {
            "devices": [asdict(b) for b in self.boards.values()],
            "username": self.global_username,
            "password": self.global_password
        }
        # Clean up None values from dicts to keep YAML clean
        for dev in data["devices"]:
            keys_to_remove = [k for k, v in dev.items() if v is None]
            for k in keys_to_remove:
                del dev[k]

        with open(self.config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def add_board(self, name: str, ip: str, linien_port: int, ssh_port: int = 22, 
                  username: str = None, password: str = None):
        """Adds or updates a board configuration."""
        new_board = BoardConfig(name, ip, linien_port, ssh_port, username, password)
        new_board.validate()
        self.boards[name] = new_board
        self.save()

    def remove_board(self, name: str):
        """Removes a board by name."""
        if name in self.boards:
            del self.boards[name]
            self.save()
            return True
        return False

    def get_board(self, name: str) -> Optional[BoardConfig]:
        """Returns the config for a specific board."""
        return self.boards.get(name)

    def list_boards(self) -> List[str]:
        """Returns a list of board names."""
        return list(self.boards.keys())

    def get_credentials(self, board_name: str):
        """Helper to get effective credentials (per-board or global)."""
        board = self.get_board(board_name)
        if not board:
            return self.global_username, self.global_password
        
        user = board.username if board.username else self.global_username
        pw = board.password if board.password else self.global_password
        return user, pw
