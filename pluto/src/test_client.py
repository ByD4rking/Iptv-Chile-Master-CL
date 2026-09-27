from client import PlutoClient

client = PlutoClient()

print("Client ID:", client.client_id)
print("Session:", type(client.session).__name__)
