from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QSplitter, QStackedWidget, 
                               QPushButton, QFrame, QHBoxLayout, QSizePolicy)
from PySide6.QtCore import Qt, Slot, Signal

class MenuButton(QPushButton):
    def __init__(self, text, on_click_callback=None):
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 10px;
                text-align: center;
            }
        """)
        if on_click_callback:
            self.clicked.connect(on_click_callback)

class MenuPage(QWidget):
    # Signals to request navigation
    sig_go_parameters = Signal()
    sig_go_advanced = Signal()
    sig_go_reflines = Signal()
    sig_go_centering = Signal()
    sig_go_manual = Signal()
    sig_go_auto = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 6 Buttons equidistant
        self.btn_params = MenuButton("Parameters", self.sig_go_parameters.emit)
        self.btn_advanced = MenuButton("Advanced settings", self.sig_go_advanced.emit)
        self.btn_reflines = MenuButton("Reference lines", self.sig_go_reflines.emit)
        self.btn_centering = MenuButton("Line centering", self.sig_go_centering.emit)
        self.btn_manual = MenuButton("Manual lock", self.sig_go_manual.emit)
        self.btn_auto = MenuButton("Auto-lock", self.sig_go_auto.emit)

        layout.addWidget(self.btn_params)
        layout.addWidget(self.btn_advanced)
        layout.addWidget(self.btn_reflines)
        layout.addWidget(self.btn_centering)
        layout.addWidget(self.btn_manual)
        layout.addWidget(self.btn_auto)

class SubPageContainer(QWidget):
    """
    A generic container for sub-pages that provides a title and a back button.
    """
    sig_back = Signal()

    def __init__(self, title, content_widget=None):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Title
        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(lbl_title)
        
        # Content (stretch factor to push back button down)
        if content_widget:
            layout.addWidget(content_widget)
        else:
             layout.addStretch()

        # Back Button centered at bottom
        btn_back = QPushButton("Back")
        btn_back.setFixedWidth(120)
        btn_back.clicked.connect(self.sig_back.emit)
        
        btn_container = QHBoxLayout()
        btn_container.addStretch()
        btn_container.addWidget(btn_back)
        btn_container.addStretch()
        
        layout.addLayout(btn_container)

class LaserControllerPage(QWidget):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- LEFT PANEL: Navigation Stack ---
        self.left_stack = QStackedWidget()
        self.left_stack.setMinimumWidth(250)
        
        # 1. Main Menu
        self.menu_page = MenuPage()
        self.left_stack.addWidget(self.menu_page)
        
        # 2. Sub Pages (Placeholders)
        self.page_parameters = SubPageContainer("Parameters")
        self.page_advanced = SubPageContainer("Advanced Settings")
        self.page_centering = SubPageContainer("Line Centering")
        self.page_manual = SubPageContainer("Manual Lock")
        self.page_auto = SubPageContainer("Auto-lock")
        
        self.left_stack.addWidget(self.page_parameters)
        self.left_stack.addWidget(self.page_advanced)
        self.left_stack.addWidget(self.page_centering)
        self.left_stack.addWidget(self.page_manual)
        self.left_stack.addWidget(self.page_auto)
        
        splitter.addWidget(self.left_stack)
        
        # --- RIGHT PANEL: Content Placeholder ---
        right_panel = QFrame()
        right_panel.setFrameShape(QFrame.StyledPanel)
        right_layout = QVBoxLayout(right_panel)
        lbl_right = QLabel("Right Content Area")
        lbl_right.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(lbl_right)
        
        splitter.addWidget(right_panel)
        
        # --- WIRING ---
        # Menu -> Pages
        self.menu_page.sig_go_parameters.connect(lambda: self.left_stack.setCurrentWidget(self.page_parameters))
        self.menu_page.sig_go_advanced.connect(lambda: self.left_stack.setCurrentWidget(self.page_advanced))
        self.menu_page.sig_go_centering.connect(lambda: self.left_stack.setCurrentWidget(self.page_centering))
        self.menu_page.sig_go_manual.connect(lambda: self.left_stack.setCurrentWidget(self.page_manual))
        self.menu_page.sig_go_auto.connect(lambda: self.left_stack.setCurrentWidget(self.page_auto))
        
        # Reference lines currently does nothing
        self.menu_page.sig_go_reflines.connect(self.on_reflines_clicked)

        # Back Buttons -> Menu
        self.page_parameters.sig_back.connect(self.go_to_menu)
        self.page_advanced.sig_back.connect(self.go_to_menu)
        self.page_centering.sig_back.connect(self.go_to_menu)
        self.page_manual.sig_back.connect(self.go_to_menu)
        self.page_auto.sig_back.connect(self.go_to_menu)
        
        # Set Splitter Ratios (Left smaller, Right larger)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

    Slot()
    def go_to_menu(self):
        self.left_stack.setCurrentWidget(self.menu_page)
        
    Slot()
    def on_reflines_clicked(self):
        self.logger.info("Reference Lines button clicked - (No Action implemented)")
