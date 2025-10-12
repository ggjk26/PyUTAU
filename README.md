# PyUTAU
A Expandable plugin (Package) for python language project. Brought back the basic features of the UTAU software in Python. 

Pre-Release Version only support Chinese (Simplified), if you want to use it in different languages (such as English or Japanese), please wait for the official release (which may take some time). 

## Features
 - Able to normally import UTAU Voice Libraries (Testing "OpenUTAU用日本語統合ライブラリー", can runs fluently)
 - Edit & Create Lyrics
 - As a Python package, you must place it in the root directory of your project.

## FUTURE PLAN
 - Throw away tkinter and use PyQt6
 - Rework at synthesis engine to play more fluent CVVC Japanese Voicebank
 - Embedded Voicebank maker
 - Setting on the top of window

PyQt6 rebuilding work is nearly complete. But it has lots of bugs such as voicebanks cannot check correctly and ust project file load failed. <br>
So, please wait it when it tested properly and can run in lowest environment requirement. <br>
dont try to git there source code because it isn't completely and it less some key code files because some technical problems<br>

## Start Page
```python
from embedded_utau import PyUTAUComponent
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

def main():
    root = tk.Tk()
    root.title("PyUtau - Embedded UTAU Tone Synthesizer")
    root.geometry("900x600")
    
    utau_component = PyUTAUComponent(root)
    utau_component.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    status_var = tk.StringVar(value="Ready")
    status_bar = tk.Label(root, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def update_status(message):
        status_var.set(message)
    
    control_frame = tk.Frame(root)
    control_frame.pack(fill=tk.X, padx=10, pady=5)
    
    tk.Button(control_frame, text="Testing Playing", 
              command=lambda: update_status("Testing Play Functions")).pack(side=tk.LEFT, padx=5)
    tk.Button(control_frame, text="clean notes", 
              command=lambda: [utau_component.clear_notes(), update_status("All notes have been cleared")]).pack(side=tk.LEFT, padx=5)
    tk.Button(control_frame, text="About", 
              command=lambda: update_status("PyUtau - Embedded UTAU Tone Synthesizer")).pack(side=tk.RIGHT, padx=5)
    
    root.mainloop()

if __name__ == "__main__":
    main()
```

Deepseek / ChatGPT -assisted code writing, If you want to get full content, please wait for offical version (0.1.0 and later) in release. <br>
If you want use it in different languages, you can push a branch and coding by yourself. <br>
This project is working in progress. NOW PROGRESS: EARLY TESTING <br>

