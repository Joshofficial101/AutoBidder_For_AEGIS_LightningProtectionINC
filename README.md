!!WARNING!!

This branch is a few updates behind main. One feature missing currently is password hashing. 
Do NOT use a real password, this version is simply for testing.

README.md: LightningBid - Setup Guide

This guide provides the necessary steps to install dependencies and run the LightningBid application on macOS and Linux systems.
Prerequisites

You must have Python 3.9 or newer and Git (if cloning) installed on your system.
1. Project Setup (First Run Only)

You have two options to get the code:
Option A: Clone the Repository (Recommended for Development)

This method automatically sets up version control for pushing changes.

    Clone the Repository:

    git clone https://github.com/Joshofficial101/AutoBidder_For_AEGIS_LightningProtectionINC.git
    cd AutoBidder_For_AEGIS_LightningProtectionINC
    git checkout mac_OS_Branch

Option B: Download ZIP File

This method is simpler for users who just need to run the application.

    Download and Unzip: Download the project as a `.zip` file from the GitHub branch and unzip it.
    Navigate to Directory: Open your terminal and navigate into the project folder.

    cd path/to/AutoBidder_For_AEGIS_LightningProtectionINC-mac_OS_Branch

Final Setup Steps (Required for both A and B)

    Grant Execution Permissions: Scripts must be explicitly granted permission to run on macOS/Linux.

    chmod +x setup.sh

    Run the Setup Script: This script creates the virtual environment and installs all dependencies.

    ./setup.sh

2. Launching the Application

Once the setup is complete, launch the GUI using the script.

./run_gui.sh

3. Login Instructions

The application will launch on the Login Screen.
Action 	Required Fields 	Feedback
Create Account 	Username, Password, Email 	Success/Failure is displayed in a modal dialog window.
Sign In 	Username, Password 	Success proceeds to the main bidding window. Failure shows an error dialog.
