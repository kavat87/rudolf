# Rudolf

![Logo](./images/rudolf.jpg)

Rudolf is an AI agent based on Ollama with WebUI interface.

## Installation

### Docker

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update

sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Driver Nvidia GPU (only if present, skip otherwise)

Is highly recommended to run AI model in general with GPU support. CPU only (supported by Ollama) has an important decrease of performances

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## First run

For the first run, we have to download models and we have to deploy our compose with internet access

```bash
# if GPU is present
docker compose -f docker-compose-full.yml up -d --remove-orphans
# if CPU only
docker compose -f docker-compose-full-nogpu.yml up -d --remove-orphans

# risk evaluation, strategy and compliance
docker exec ollama ollama pull saki007ster/CybersecurityRiskAnalyst

# general purpose
docker exec ollama ollama pull mistral:latest

# general purpose more precise (require resources)
docker exec ollama ollama pull gpt-oss:20b

# general purpose more precise (require very high resources)
docker exec ollama ollama pull gpt-oss:120b

# scripting and technical answers
docker exec ollama ollama pull deepseek-r1

# list ollama model downloaded
docker exec ollama ollama list

# stop current full compose
# if GPU is present
docker compose -f docker-compose-full.yml down
# if CPU only
docker compose -f docker-compose-full-nogpu.yml down
```

## Run

After previous step we can run compose with internet limitation

```bash
# if GPU is present
docker compose up -d --remove-orphans
# if CPU only
docker compose -f docker-compose-nogpu.yml up -d --remove-orphans
```

If you want to include Rudolf in your [Erebus-AI](https://github.com/kavat/Erebus-AI) deployment run different yml
Run ensuring you have erebus_shared network created

```bash
root@manaone:/opt/rudolf# docker network ls
NETWORK ID     NAME                        DRIVER    SCOPE
8735c19a1eb9   erebus_shared               bridge    local
```

If it is not present, refers to [Erebus-AI](https://github.com/kavat/Erebus-AI) deployment guide.
When all it is ok, proceeding with:

```bash
# if GPU is present
docker compose -f docker-compose-erebus.yml up -d --remove-orphans
# if CPU only
docker compose -f docker-compose-erebus-nogpu.yml up -d --remove-orphans
```

## Rudolf WebUI

Launch [http://localhost:8080](http://localhost:8080) and starting your conversion

## API

```bash
curl -N http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Ask me hello",
    "model": "mistral:latest",
    "thinking": false
  }'
```

## Tokenizers used

Tokenizers have been downloaded from [huggingface](https://huggingface.co/) and are listed below:

````text
https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2/resolve/main/tokenizer.json?download=true
https://huggingface.co/deepseek-ai/DeepSeek-R1/resolve/main/tokenizer.json?download=true
https://huggingface.co/openai/gpt-oss-20b/resolve/main/tokenizer.json?download=true
https://huggingface.co/openai/gpt-oss-120b/resolve/main/tokenizer.json?download=true
https://huggingface.co/saki007ster/Cybersecurity-7B-v0.2-Q6-mlx/resolve/main/tokenizer.json
```
