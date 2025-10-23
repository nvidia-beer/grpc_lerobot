FROM huggingface/lerobot-cpu

# Install gRPC and YAML dependencies
COPY client/docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

