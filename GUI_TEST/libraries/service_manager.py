from PySide6.QtCore import QObject, Signal, Slot
import os
import yaml

class ServiceManager(QObject):
    sig_board_list_updated = Signal(list) 
    sig_error = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # --- PATH LOGIC ---
        # 1. Try the path defined in config.yaml
        hardware_path = self.config.get('paths', {}).get('hardware', '')
        
        # 2. If config path is absolute, use it. If relative, join with script dir.
        if not os.path.isabs(hardware_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            hardware_path = os.path.join(base_dir, hardware_path)

        self.board_list_path = os.path.join(hardware_path, "board_list.yaml")
        
        print(f"DEBUG: ServiceManager looking for board list at: {self.board_list_path}", flush=True)

    def _read_yaml(self):
        if not os.path.exists(self.board_list_path):
            print(f"DEBUG: board_list.yaml not found at {self.board_list_path}", flush=True)
            return {'devices': []}
        
        try:
            with open(self.board_list_path, 'r') as f:
                data = yaml.safe_load(f)
                if data is None: return {'devices': []}
                return data
        except Exception as e:
            err = f"Failed to read board list: {e}"
            print(f"ERROR: {err}", flush=True)
            self.sig_error.emit(err)
            return {'devices': []}

    def _save_yaml(self, data):
        try:
            # Ensure directory exists before writing
            os.makedirs(os.path.dirname(self.board_list_path), exist_ok=True)
            
            with open(self.board_list_path, 'w') as f:
                yaml.safe_dump(data, f, default_flow_style=False)
            print("DEBUG: board_list.yaml saved.", flush=True)
        except Exception as e:
            err = f"Failed to save board list: {e}"
            print(f"ERROR: {err}", flush=True)
            self.sig_error.emit(err)

    @Slot()
    def load_boards(self):
        """Triggered on startup or refresh."""
        print("DEBUG: Loading boards...", flush=True)
        data = self._read_yaml()
        device_list = data.get('devices', [])
        print(f"DEBUG: Found {len(device_list)} devices.", flush=True)
        self.sig_board_list_updated.emit(device_list)

    @Slot(str, str, str, str)
    def add_board(self, name, ip, linien_port, ssh_port):
        print(f"SERVICE: Adding board '{name}'...", flush=True)
        data = self._read_yaml()
        if 'devices' not in data or data['devices'] is None:
            data['devices'] = []

        new_device = {
            'name': name,
            'ip': ip,
            'linien_port': int(linien_port) if linien_port.isdigit() else 18862,
            'ssh_port': int(ssh_port) if ssh_port.isdigit() else 22,
            'username': 'root',
            'password': 'root'
        }

        data['devices'].append(new_device)
        self._save_yaml(data)
        self.sig_board_list_updated.emit(data['devices'])

    @Slot(str)
    def remove_board(self, board_name):
        print(f"SERVICE: Removing board '{board_name}'...", flush=True)
        data = self._read_yaml()
        current_list = data.get('devices', [])
        new_list = [d for d in current_list if d.get('name') != board_name]
        data['devices'] = new_list
        self._save_yaml(data)
        self.sig_board_list_updated.emit(new_list)