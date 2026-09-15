import json

class External_Json():
    def deserialize(self, file:str):
        with open(file) as f:
            data = f.read()
            return json.loads(data)