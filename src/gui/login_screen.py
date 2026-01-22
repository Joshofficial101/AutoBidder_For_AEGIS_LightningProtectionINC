import flet as ft
from pathlib import Path
from typing import Callable, Any, Optional, List
import sys
# FIX: Explicitly import constant classes that were failing in Windows
from flet import Colors, FontWeight, MainAxisAlignment, BoxShadow, CrossAxisAlignment

class LoginScreen(ft.Container):
    """
    A reusable Flet component for the User Login/Signup interface.
    """
    
    def __init__(self, on_login: Callable[[str, str], Any], on_create_account: Callable[[str, str, str], Any]):
        
        self.is_signup_mode = False
        self._on_login = on_login
        self._on_create_account = on_create_account
        self.logo_path = self._resolve_logo_path()
        self.logo_container = self._build_logo_container()
        
        self.title_text = ft.Text("Welcome Back", size=24, weight=FontWeight.BOLD, key="title")
        self.subtitle_text = ft.Text(
            "Sign in to create lightning protection bids",
            size=12,
            color=Colors.GREY_600
        )
        
        # --- Input Fields ---
        self.username_field = ft.TextField(
            label="Username",
            prefix_icon=ft.Icon(ft.Icons.PERSON), 
            width=300,
            autofocus=True,
            border_radius=8,
            filled=True,
            bgcolor=Colors.GREY_100
        )
        
        self.password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icon(ft.Icons.LOCK), 
            width=300,
            border_radius=8,
            filled=True,
            bgcolor=Colors.GREY_100,
            on_submit=lambda e: self._handle_submission(),
        )
        
        self.email_field = ft.TextField(
            label="Email",
            prefix_icon=ft.Icon(ft.Icons.EMAIL), 
            width=300,
            visible=False,
            border_radius=8,
            filled=True,
            bgcolor=Colors.GREY_100
        )
        
        # --- Buttons ---
        
        # FIX: Use imported FontWeight
        self.main_button = ft.ElevatedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.LOGIN), ft.Text("SIGN IN", weight=FontWeight.BOLD)],
                alignment=MainAxisAlignment.CENTER,
                spacing=10
            ),
            width=300,
            height=44,
            bgcolor=Colors.BLUE_700,
            color=Colors.WHITE,
            on_click=lambda e: self._handle_submission(),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=2,
            )
        )
        
        self.toggle_button = ft.TextButton(
            "Create Account",
            width=300,
            on_click=self._toggle_mode,
        )
        
        # Main Container structure
        super().__init__(
            width=420,
            height=540,
            padding=28,
            border_radius=16,
            # FIX: Use imported Colors
            bgcolor=Colors.WHITE,
            # FIX: Use imported BoxShadow and Colors
            shadow=BoxShadow(blur_radius=10, color=Colors.BLACK26),
            alignment=ft.alignment.center,
            expand=False,
            content=ft.Column(
                [
                    self.logo_container,
                    self.title_text,
                    self.subtitle_text,
                    self.username_field,
                    self.password_field,
                    self.email_field, 
                    ft.Container(height=10),
                    self.main_button,
                    self.toggle_button,
                    ft.Text(
                        "Protected by AES-256 encryption",
                        size=10,
                        color=Colors.GREY_500
                    )
                ],
                # FIX: Use imported CrossAxisAlignment and MainAxisAlignment
                horizontal_alignment=CrossAxisAlignment.CENTER,
                alignment=MainAxisAlignment.CENTER,
                spacing=12,
                tight=True
            )
        )

    def _resolve_logo_path(self) -> Optional[str]:
        """Find a local logo file if present.
        
        Images are stored in the assets folder to persist independently
        of user data files in the inputs folder.
        """
        root_dir = _get_resource_root()
        candidates = [
            # Primary location: assets folder (persists even when inputs are cleared)
            root_dir / "assets" / "company_logo.png",
            root_dir / "assets" / "company_logo.jpg",
            root_dir / "assets" / "aegis_logo.png",
            root_dir / "assets" / "aegis_logo.jpg",
            root_dir / "assets" / "logo.png",
            root_dir / "assets" / "logo.jpg",
            # Fallback locations
            root_dir / "aegis_logo.png",
            root_dir / "aegis_logo.jpg",
            root_dir / "logo.png",
            root_dir / "logo.jpg",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None
    
    def _build_logo_container(self) -> ft.Control:
        """Create logo container with fallback placeholder."""
        if self.logo_path:
            logo_control = ft.Image(
                src=self.logo_path,
                width=320,
                height=100,
                fit=ft.ImageFit.CONTAIN
            )
        else:
            logo_control = ft.Text(
                "AEGIS Lightning Protection, Inc.",
                size=16,
                color=Colors.GREY_700,
                weight=FontWeight.BOLD
            )
        
        return ft.Container(
            content=logo_control,
            height=110,
            alignment=ft.alignment.center,
            padding=10,
            bgcolor=Colors.GREY_50,
            border=ft.border.all(1, Colors.GREY_200),
            border_radius=12
        )

    def _toggle_mode(self, e):
        """Switches between login and signup modes."""
        self.is_signup_mode = not self.is_signup_mode
        
        # Get the icon and text controls from the container content
        icon_control = self.main_button.content.controls[0]
        text_control = self.main_button.content.controls[1]
        
        # Update UI elements based on the new mode
        if self.is_signup_mode:
            self.title_text.value = "Create Account"
            self.subtitle_text.value = "Create your account to start bidding"
            
            text_control.value = "CREATE ACCOUNT"
            icon_control.name = ft.Icons.PERSON_ADD 
            
            self.toggle_button.text = "Back to Sign In"
            self.email_field.visible = True
        else:
            self.title_text.value = "Welcome Back"
            self.subtitle_text.value = "Sign in to create lightning protection bids"
            
            text_control.value = "SIGN IN"
            icon_control.name = ft.Icons.LOGIN 
            
            self.toggle_button.text = "Create Account"
            self.email_field.visible = False

        # Update controls
        icon_control.update()
        text_control.update()
        self.title_text.update()
        self.subtitle_text.update()
        self.email_field.update()
        self.toggle_button.update()
        self.update()

    def _handle_submission(self):
        """Passes the input values to the main application's handler."""
        username = self.username_field.value.strip()
        password = self.password_field.value
        email = self.email_field.value.strip() if self.is_signup_mode else ""
        
        # Clear sensitive data after attempt
        self.password_field.value = ""
        self.password_field.update()
        
        if self.is_signup_mode:
            self._on_create_account(username, password, email)
        else:
            self._on_login(username, password)

def create_login_view(on_login_submit, on_create_account_click):
    """Creates the centered view containing the LoginScreen."""
    login_screen = LoginScreen(on_login_submit, on_create_account_click)
    
    root_dir = _get_resource_root()
    # Background image is stored in assets folder to persist independently of user data
    background_image = root_dir / "assets" / "login_background.jpg"
    background_src = str(background_image) if background_image.exists() else None
    
    # Use explicit large dimensions with COVER to ensure full-bleed on any monitor
    background_layer = ft.Container(
        expand=True,
        bgcolor=Colors.BLACK,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        content=ft.Image(
            src=background_src,
            fit=ft.ImageFit.COVER,
            width=4000,
            height=3000
        )
    ) if background_src else ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[Colors.BLUE_50, Colors.BLUE_100, Colors.GREY_100]
        )
    )
    
    # Add a dark overlay so the login card pops
    overlay_layer = ft.Container(
        expand=True,
        bgcolor=Colors.with_opacity(0.45, Colors.BLACK)
    )
    
    return ft.View(
        "/login",
        [
            ft.Stack(
                expand=True,
                controls=[
                    background_layer,
                    overlay_layer,
                    ft.Container(
                        expand=True,
                        alignment=ft.alignment.center,
                        content=login_screen
                    )
                ]
            )
        ],
        # FIX: Use imported MainAxisAlignment and CrossAxisAlignment
        vertical_alignment=MainAxisAlignment.CENTER,
        horizontal_alignment=CrossAxisAlignment.CENTER,
        padding=0,
        bgcolor=Colors.BLACK
    )


def _get_resource_root() -> Path:
    """Resolve the base path for bundled resources (PyInstaller/cx_Freeze)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base if base.exists() else Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]