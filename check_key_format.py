import os
from dotenv import load_dotenv

def check_format():
    load_dotenv()
    pk = os.getenv('LIGHTER_API_PRIVATE_KEY', '')
    
    print(f"Key Length: {len(pk)}")
    print(f"Starts with '0x': {pk.startswith('0x')}")
    try:
        if pk.startswith('0x'):
            int(pk, 16)
        else:
            int(pk, 16)
        print("Is Hex: Yes")
    except:
        print("Is Hex: No")

    # Check if it matches the Public Key from screenshot
    # Public key starts with: 2ac9fc1a4ee015ba...
    public_key_start = "2ac9fc1a4ee0"
    if pk.replace('0x', '').lower().startswith(public_key_start):
        print("\n🚨 MATCH FOUND: The 'Private Key' in .env MATCHES the Public Key from your screenshot!")
        print("You pasted the PUBLIC KEY instead of the PRIVATE KEY.")
    else:
        print("\nDoes not match the Public Key prefix.")

if __name__ == "__main__":
    check_format()
