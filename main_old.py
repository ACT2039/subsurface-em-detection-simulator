import sys
from PyQt6.QtWidgets import QApplication
from gui import RadarGUI

def main():
    app = QApplication(sys.argv)
    
    # Modern Dark/Light Fusion-based style
    app.setStyle("Fusion")
    
    # Add professional Scientific Light CSS style
    style = """
    QWidget {
        font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
        font-size: 13px;
        color: #333333;
        background-color: #F8F9FA;
    }
    QMainWindow, QSplitter::handle {
        background-color: #E9ECEF;
    }
    QPushButton {
        background-color: #007BFF;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 12px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #0056B3;
    }
    QPushButton:pressed {
        background-color: #004085;
    }
    QGroupBox {
        font-weight: bold;
        border: 1px solid #CED4DA;
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 15px;
        background-color: #FFFFFF;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 5px;
        left: 10px;
        top: -6px;
        background-color: #FFFFFF;
        color: #495057;
    }
    QLineEdit, QComboBox {
        padding: 6px;
        border: 1px solid #CED4DA;
        border-radius: 4px;
        background-color: #FFFFFF;
        color: #212529;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #80BDFF;
        background-color: #FFFFFF;
        outline: none;
    }
    QComboBox::drop-down {
        border-left: 1px solid #CED4DA;
    }
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    """
    app.setStyleSheet(style)
    
    # Create main window
    window = RadarGUI()
    window.show()
    
    sys.exit(app.exec())



if __name__ == '__main__':
    main()
