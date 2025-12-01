#!/usr/bin/env bash
set -e
BANNER='
 ___      ___  __  ___________  ______    
|"  \    /"  ||" \("     _   ")/    " \   
 \   \  //  / ||  |)__/  \\__/// ____  \  
  \\  \/ . ./  |:  |   \\_ /  /  /    ) :) 
   \.    //   |.  |   |.  | (: (____/ //  
    \\   /    /\  |\  \:  |  \        /   
     \__/    (__\_|_)  \__|   \"_____/    
'
echo "$BANNER"
echo "VITO Discord bot installer"
echo

# Create venv, install deps, gather keys, write settings.json
read -p "Discord Bot Token: " DISCORD_TOKEN
read -p "Creator Discord ID (numeric): " CREATOR_ID
read -p "Comma-separated Admin Discord IDs (numeric, optional): " ADMINS
read -p "Gemini API Key (Google Generative API key): " GEMINI_KEY
read -p "OpenRouter API Key (for Venice/Dolphin models): " OPENROUTER_KEY

# Normalize admins into JSON array
IFS=',' read -ra ADDR <<< "$ADMINS"
ADM_ARRAY="["
for i in "${ADDR[@]}"; do
  trimmed=$(echo "$i" | xargs)
  if [ -n "$trimmed" ]; then
    ADM_ARRAY="$ADM_ARRAY\"$trimmed\","
  fi
done
ADM_ARRAY="${ADM_ARRAY%,}]"

cat > settings.json <<EOF
{
  "discord_token": "$DISCORD_TOKEN",
  "creator": "$CREATOR_ID",
  "admins": $ADM_ARRAY,
  "gemini_api": "$GEMINI_KEY",
  "openrouter_api": "$OPENROUTER_KEY",
  "model_gemini": "gemini-2.5-flash-lite",
  "model_venice": "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
}
EOF

echo "Creating Python venv..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Installation complete. Run './install.sh' and choose Start, or activate the venv and run:"
echo "source venv/bin/activate && python3 main.py"
