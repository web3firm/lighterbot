import lighter
import inspect

print("SignerClient signature:")
try:
    print(inspect.signature(lighter.SignerClient.__init__))
except Exception as e:
    print(f"Could not get signature: {e}")

print("\nMethod resolution order:")
print(lighter.SignerClient.mro())

print("\nDir:")
print(dir(lighter.SignerClient))
