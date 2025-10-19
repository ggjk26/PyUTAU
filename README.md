# PyUTAU
## Special Thanks
 - [1ndex_qwq](https://steamcommunity.com/profiles/76561199806244588 "Third-Party Supporter")
 - [Feng](https://steamcommunity.com/profiles/76561199511541101 "Third-Party Supporter")
 - [OpenUTAU](https://openutau.com "Offical Independent Version")
 
## About PyUTAU
PyUTAU is a Expandable Embedded Package for python project.<br>
A based Python Core, and rebuild the editor. Althoght it can import UST file, but not support midi & USTX project file import
This project is not available because it haven't fully support main languages and have some hard to fixed problems
If you want another features, you can push a issue
BASED PyQt6

## Competitable
### Suggest Platform
 - Python 3.9.0 and later

### Singer Support
 - UTAU

## fast start
Now I'll fix up some bugs so I haven't upload any release on it and wait it until it have a bugless pre-release version

## Start Page
PyQt6 Code
```python
def main():
    print("=" * 50)
    print("PyUTAU Studio Plugin")
    print("=" * 50)
    
    # add embedded_utau path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    print(f"Work Dir: {current_dir}")
    
    try:
        from PyQt6.QtWidgets import QApplication
        
        import embedded_utau.main_window as main_window_module
        
        app = QApplication(sys.argv)
        app.setApplicationName("PyUTAU Studio")
        app.setApplicationVersion("0.1.0")
        
        window = main_window_module.MainWindow()
        window.show()
        
        print("=" * 50)
        print("Plugin Launched!")
        print("=" * 50)
        
        return app.exec()
        
    except Exception as e:
        print(f"✗ Setup Failed!: {e}")
        import traceback
        traceback.print_exc()
        
        print("\nTry again with another ways...")
        try:
            from PyQt6.QtWidgets import QApplication

            class SimpleMainWindow(QApplication):
                def __init__(self):
                    super().__init__(sys.argv)
                    from PyQt6.QtWidgets import QMainWindow, QLabel
                    self.window = QMainWindow()
                    self.window.setWindowTitle("PyUTAU Studio - debug mode")
                    self.window.setGeometry(100, 100, 800, 600)
                    label = QLabel("PyUTAU Studio\n\nBecuse of Some Problem, debug mode is running.\nPlease check consle output information.")
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.window.setCentralWidget(label)
                    self.window.show()
            
            simple_app = SimpleMainWindow()
            return simple_app.exec()
            
        except Exception as e2:
            print(f"Setup Failed, Please push a issue with your consle error information (deleted private information such as project path and structure): {e2}")
            input("Press 'Enter' to exit this plugin...")
            return 1

if __name__ == "__main__":
    sys.exit(main())
```

## OpenSource LICENSE
NOW NOT AVAILABLE SO NO LICENSE ITO USE
CODES HERE WERE LEGACY TKINTER VERSION AND LESS ON SOME KEY FILES


