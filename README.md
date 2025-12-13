README.md: LightningBid - Setup Guide

This guide provides the necessary steps to install dependencies and run the LightningBid application on Windows Systems
Prerequisites

You must have Python 3.9 or newer and Git (if cloning) installed on your system.
1. Project Setup (First Run Only)

You have two options to get the code:
Option A: Clone the Repository (Recommended for Development)

This method automatically sets up version control for pushing changes.

    Clone the Repository:

    git clone https://github.com/Joshofficial101/AutoBidder_For_AEGIS_LightningProtectionINC.git
    cd AutoBidder_For_AEGIS_LightningProtectionINC
    git checkout Windows_Branch

Option B: Download ZIP File

This method is simpler for users who just need to run the application.

    Download and Unzip: Download the project as a `.zip` file from the GitHub branch and unzip it.
    Navigate to Directory: Open your terminal and navigate into the project folder.

    cd path/to/AutoBidder_For_AEGIS_LightningProtectionINC-Windows_Branch

Final Setup Steps (Required for both A and B)

    Run the Setup Script: This script creates the virtual environment and installs all dependencies.

    setup.cmd

2. Launching the Application

Once the setup is complete, launch the GUI using the simplified script.

run_gui.cmd

3. Login Instructions

The application will launch on the Login Screen.
Action 	Required Fields 	Feedback
Create Account 	Username, Password, Email 	Success/Failure is displayed in a modal dialog window.
Sign In 	Username, Password 	Success proceeds to the main bidding window. Failure shows an error dialog.