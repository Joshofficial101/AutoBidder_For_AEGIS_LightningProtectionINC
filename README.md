README.md: LightningBid - Setup Guide

This guide provides the necessary steps to install dependencies and run the LightningBid application on Windows Systems
Prerequisites. MacOS users see mac_OS_Branch.

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

4. Using the application

After loggin in, use the file selection buttons to select the necessary documents for creating a bid

<img width="462" height="134" alt="Screenshot 2025-12-15 at 5 19 51 PM" src="https://github.com/user-attachments/assets/a2f5a176-1ba7-46ac-8916-922702d1b6e1" />

We have provided two documents to use in the data -> inputs folder.
Use the parse PDF function to fill in the boxes, use the load Excel button to pull information from the pricing document, then press calculate bid to see the output.

<img width="617" height="132" alt="Screenshot 2025-12-15 at 5 24 34 PM" src="https://github.com/user-attachments/assets/eca44583-a57d-4e55-b5f0-0de2f2c1fa44" />

After your build sheet is created, you can use the export buttons to save the document as a PDF or Excel to your preferred file loaction.

<img width="1195" height="665" alt="Screenshot 2025-12-15 at 5 28 07 PM" src="https://github.com/user-attachments/assets/eda6e594-f9ca-48bd-816c-653813aeae3c" />


