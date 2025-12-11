"""
Run the LightningBid GUI Application

This is the entry point for running the Flet GUI.
Run with: python -m src.gui.run_gui
"""

import flet as ft
from src.gui.main_window import main

if __name__ == "__main__":
    ft.app(target=main)


