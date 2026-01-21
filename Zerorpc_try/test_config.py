import sys
from pathlib import Path

# Add the parent directory to sys.path to import GettingStarted_lib
sys.path.append(str(Path(__file__).parent.parent))

from GettingStarted_lib.Interface import Interface
from GettingStarted_lib.config_manager import ConfigManager

def test_config():
    # 1. Test ConfigManager directly
    print("--- Testing ConfigManager ---")
    cm = ConfigManager()
    print(f"Boards found: {cm.list_boards()}")
    
    # 2. Add a temporary board
    print("Adding 'TestBoard'...")
    cm.add_board("TestBoard", "1.1.1.1", 1234, username="test_user", password="test_password")
    
    # Reload and check
    cm2 = ConfigManager()
    if "TestBoard" in cm2.list_boards():
        print("Success: TestBoard found after reload.")
        board = cm2.get_board("TestBoard")
        print(f"TestBoard IP: {board.ip}, User: {board.username}")
    else:
        print("Error: TestBoard not found after reload.")
        return

    # 3. Test Interface (Note: we don't connect here to avoid hardware errors)
    print("\n--- Testing Interface with Direct Parameters ---")
    # We'll mock the connect to avoid exceptions
    class MockInterface(Interface):
        def _connect(self):
            print(f"(Mock) Successfully connected to {self.host}:{self.linien_port}")
            pass
        def _basic_configure(self):
            pass

    board = cm2.get_board("RedPitaya_K")
    user, pw = cm2.get_credentials("RedPitaya_K")
    infra = MockInterface(
        host=board.ip,
        linien_port=board.linien_port,
        username=user,
        password=pw,
        ssh_port=board.ssh_port
    )
    print(f"Interface host: {infra.host}")
    
    print("Removing 'TestBoard' via ConfigManager directly (Interface doesn't handle this anymore)...")
    cm2.remove_board("TestBoard")
    
    if "TestBoard" not in cm2.list_boards():
        print("Success: TestBoard removed.")
    else:
        print("Error: TestBoard still exists.")
        return

    print("\nAll config tests passed!")

if __name__ == "__main__":
    test_config()
