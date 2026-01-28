from PySide6.QtCore import QObject, Signal, Slot
import os
import yaml
import logging
from .logging_config import setup_logging

class ServiceManager(QObject):
    sig_board_list_updated = Signal(list) 
    sig_error = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config

        # Setup Logging
        log_path = self.config.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'service_manager.log')
        self.logger = logging.getLogger('ServiceManager')
        setup_logging(self.logger, log_file)
        self.logger.info("ServiceManager initialized.")
        
        # --- PATH LOGIC ---
        # 1. Try the path defined in config.yaml
        hardware_path = self.config.get('paths', {}).get('hardware', '')
        
        # 2. If config path is absolute, use it. If relative, join with script dir.
        if not os.path.isabs(hardware_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            hardware_path = os.path.join(base_dir, hardware_path)

        self.board_list_path = os.path.join(hardware_path, "board_list.yaml")
        
        self.logger.info(f"ServiceManager looking for board list at: {self.board_list_path}")

    # -------------------------------------------------------------------------
    # YAML FILES METHODS
    # -------------------------------------------------------------------------

    # ---- Red Pitaya boards ----

    def _read_boards_yaml(self):
        if not os.path.exists(self.board_list_path):
            self.logger.info(f"board_list.yaml not found at {self.board_list_path}")
            return {'devices': []}
        
        try:
            with open(self.board_list_path, 'r') as f:
                data = yaml.safe_load(f)
                if data is None: return {'devices': []}
                return data
        except Exception as e:
            err = f"Failed to read board list: {e}"
            self.logger.error(f"{err}")
            self.sig_error.emit(err)
            return {'devices': []}

    def _save_boards_yaml(self, data):
        try:
            # Ensure directory exists before writing
            os.makedirs(os.path.dirname(self.board_list_path), exist_ok=True)
            
            with open(self.board_list_path, 'w') as f:
                yaml.safe_dump(data, f, default_flow_style=False)
            self.logger.info("board_list.yaml saved.")
        except Exception as e:
            err = f"Failed to save board list: {e}"
            self.logger.error(f"{err}")
            self.sig_error.emit(err)

    @Slot()
    def load_boards(self):
        """Triggered on startup or refresh."""
        self.logger.info("Loading boards...")
        data = self._read_boards_yaml()
        device_list = data.get('devices', [])
        self.logger.info(f"Found {len(device_list)} devices.")
        self.sig_board_list_updated.emit(device_list)

    @Slot(str, str, str, str)
    def add_board(self, name, ip, linien_port, ssh_port):
        self.logger.info(f"Adding board '{name}'...")
        data = self._read_boards_yaml()
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
        self._save_boards_yaml(data)
        self.sig_board_list_updated.emit(data['devices'])

    @Slot(str)
    def remove_board(self, board_name):
        self.logger.info(f"Removing board '{board_name}'...")
        data = self._read_boards_yaml()
        current_list = data.get('devices', [])
        new_list = [d for d in current_list if d.get('name') != board_name]
        data['devices'] = new_list
        self._save_boards_yaml(data)
        self.sig_board_list_updated.emit(new_list)

    # ---- Reference lines ----

    # ---- Red Pitaya parameters ----

    # ---- Circuits parameters ----

    # -------------------------------------------------------------------------
    # ZERORPC METHODS
    # -------------------------------------------------------------------------


    # -------------------------------------------------------------------------
    # GRAFANA METHODS
    # -------------------------------------------------------------------------

