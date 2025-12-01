#!/bin/bash

# ASCII Art
print_header() {
    clear
    echo " ___      ___  __  ___________  ______     "
    echo "|\"  \    /\"  ||\" \(\"     _   \")/    \" \    "
    echo " \   \  //  / ||  |)__/  \\\\__/// ____  \   "
    echo "  \\\\  \/. ./  |:  |   \\\\_ /  /  /    ) :) "
    echo "   \.    //   |.  |    |.  | (: (____/ //   "
    echo "    \\\\   /    /\\  |\\   \:  |  \        /    "
    echo "     \__/    (__\_|_)   \__|   \\\"_____/     "
    echo "                                          "
}

# Install Function
do_install() {
    echo "Installing dependencies..."
    
    # Check for python3
    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 could not be found."
        exit 1
    fi

    # Create VENV
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "Virtual environment created."
    fi

    # Install libs
    ./venv/bin/pip install -r requirements.txt
    
    echo "------------------------------------------------"
    echo "Configuration Setup"
    echo "------------------------------------------------"
    
    read -p "Creator Discord ID (Your ID): " creator_id
    read -p "Discord Bot Token: " discord_token
    read -p "Gemini API Key: " gemini_key
    read -p "Venice/OpenRouter API Key: " venice_key
    read -p "Admin Discord IDs (comma separated, optional): " admin_ids

    echo "Setting everything up..."

    # Create settings.json
    cat > settings.json <<EOF
{
  "creator_id": "$creator_id",
  "admin_ids": "$admin_ids",
  "discord_token": "$discord_token",
  "gemini_key": "$gemini_key",
  "venice_key": "$venice_key",
  "model_gemini": "gemini-2.0-flash-lite-preview",
  "model_venice": "venice/llama-3.1-405b"
}
EOF
    # NOTE: "gemini-2.5-flash-lite" is not a standard public endpoint yet. 
    # I have used "gemini-2.0-flash-lite-preview" which is the current fast model.
    # You can edit settings.json later if 2.5 becomes available.

    # Create memory file
    if [ ! -f "memory.json" ]; then
        echo "{}" > memory.json
    fi

    echo "Installation complete."
    read -p "Press Enter to return to menu..."
}

# Start Function
do_start() {
    if [ ! -d "venv" ]; then
        echo "Error: venv not found. Please run Install first."
        read -p "Press Enter..."
        return
    fi
    echo "Starting Vito..."
    ./venv/bin/python3 main.py
    read -p "Bot stopped. Press Enter..."
}

# Menu Loop
while true; do
    print_header
    echo "1. Start"
    echo "2. Install"
    echo "3. Exit"
    read -p "Select option: " choice

    case $choice in
        1) do_start ;;
        2) do_install ;;
        3) exit 0 ;;
        *) echo "Invalid option." ;;
    esac
done