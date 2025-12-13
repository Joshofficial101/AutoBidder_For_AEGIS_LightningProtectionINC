import flet as ft
from typing import Callable, Any
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
        
        # --- Input Fields ---
        self.username_field = ft.TextField(
            label="Username",
            prefix_icon=ft.Icon('person'), 
            width=300,
            autofocus=True,
        )
        
        self.password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            prefix_icon=ft.Icon('lock'), 
            width=300,
            on_submit=lambda e: self._handle_submission(),
        )
        
        self.email_field = ft.TextField(
            label="Email",
            prefix_icon=ft.Icon('email'), 
            width=300,
            visible=False,
        )
        
        # --- Buttons ---
        
        # FIX: Use imported FontWeight
        self.main_button_content = ft.Row(
            [ft.Icon('login'), ft.Text("SIGN IN", weight=FontWeight.BOLD)],
            # FIX: Use imported MainAxisAlignment
            alignment=MainAxisAlignment.CENTER,
            spacing=10
        )
        
        # FIX: Define the main button as a clickable Container (mimics Elevated button)
        self.main_button = ft.Container(
            content=self.main_button_content,
            width=300,
            height=40,
            border_radius=5,
            # FIX: Use imported Colors
            bgcolor=Colors.BLUE_600,
            on_click=lambda e: self._handle_submission(),
            # FIX: Use imported BoxShadow and Colors
            shadow=BoxShadow(blur_radius=2, color=Colors.BLACK26),
            padding=ft.padding.symmetric(horizontal=10),
        )
        
        self.toggle_button = ft.TextButton(
            "Create Account",
            width=300,
            on_click=self._toggle_mode,
        )
        
        # Main Container structure
        super().__init__(
            width=400,
            padding=30,
            border_radius=10,
            # FIX: Use imported Colors
            bgcolor=Colors.WHITE,
            # FIX: Use imported BoxShadow and Colors
            shadow=BoxShadow(blur_radius=10, color=Colors.BLACK26),
            content=ft.Column(
                [
                    # FIX: Use imported FontWeight
                    ft.Text("LightningBid Login", size=24, weight=FontWeight.BOLD, key="title"),
                    ft.Divider(),
                    self.username_field,
                    self.password_field,
                    self.email_field, 
                    ft.Container(height=10),
                    self.main_button,
                    self.toggle_button,
                ],
                # FIX: Use imported CrossAxisAlignment and MainAxisAlignment
                horizontal_alignment=CrossAxisAlignment.CENTER,
                alignment=MainAxisAlignment.CENTER,
                spacing=10
            )
        )

    def _toggle_mode(self, e):
        """Switches between login and signup modes."""
        self.is_signup_mode = not self.is_signup_mode
        
        # Get the icon and text controls from the container content
        icon_control = self.main_button_content.controls[0]
        text_control = self.main_button_content.controls[1]
        
        # Update UI elements based on the new mode
        if self.is_signup_mode:
            self.content.controls[0].value = "Create Account"
            
            text_control.value = "CREATE ACCOUNT"
            icon_control.name = 'person_add' 
            
            self.toggle_button.text = "Back to Sign In"
            self.email_field.visible = True
        else:
            self.content.controls[0].value = "LightningBid Login"
            
            text_control.value = "SIGN IN"
            icon_control.name = 'login' 
            
            self.toggle_button.text = "Create Account"
            self.email_field.visible = False

        # Update controls
        icon_control.update()
        text_control.update()
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
    
    return ft.View(
        "/login",
        [
            ft.Container(
                content=login_screen,
                alignment=ft.alignment.center,
                expand=True
            )
        ],
        # FIX: Use imported MainAxisAlignment and CrossAxisAlignment
        vertical_alignment=MainAxisAlignment.CENTER,
        horizontal_alignment=CrossAxisAlignment.CENTER
    )