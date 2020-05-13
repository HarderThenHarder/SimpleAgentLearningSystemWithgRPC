import os

os.system("python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. envData.proto")