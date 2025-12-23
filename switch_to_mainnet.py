import os

# Mainnet vs Testnet URLs
MAINNET_URL = "https://mainnet.zklighter.elliot.ai"

env_path = '.env'
new_lines = []

if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
         with open(env_path, 'r') as f:
            lines = f.readlines()
            
    for line in lines:
        if line.startswith('LIGHTER_API_URL='):
            # Comment out old one if needed, or just replace
            pass 
        elif line.startswith('# LIGHTER_API_URL='):
            pass
        else:
            new_lines.append(line)

# Prepend the new URL or find a place for it. 
# Better strategy: Replace the line if found, otherwise append.
new_lines = []
found = False

for line in lines:
    if line.strip().startswith('LIGHTER_API_URL='):
        new_lines.append(f"LIGHTER_API_URL={MAINNET_URL}\n")
        found = True
    else:
        new_lines.append(line)

if not found:
    new_lines.insert(0, f"LIGHTER_API_URL={MAINNET_URL}\n")

with open(env_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"✅ Switched to Mainnet: {MAINNET_URL}")
