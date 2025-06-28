import os

from app.gradio_ui import gr_interface

def main():
    """Launch the Gradio admin UI"""
    ui_port = int(os.getenv("UI_PORT", 7860))
    gr_interface.launch(server_name="0.0.0.0", server_port=ui_port)

if __name__ == "__main__":
    main()