# Flask App Deployment (Docker + DigitalOcean + Caddy + HTTPS)

## 1. Create Droplet (Ubuntu 24.04)

* Use 1 vCPU, 1GB RAM (~$6–$10/month on DigitalOcean)
* Set up SSH key for login or reset password if needed

## 2. SSH into Droplet

``` bash
ssh root@your_droplet_ip
```

## 3. Create and Enable Swap (MANDATORY for 1GB/2GB Droplets)

> 💡 **Tip:**  
> Swap space prevents out-of-memory crashes during database migrations and production spikes. This step is required for all small droplets!

``` bash
fallocate -l 1G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
free -m
```

*You should see Swap: with 1023 total after running `free -m`. Swap is now persistent and will survive reboots.*

## 4. Install Docker and Docker Compose

``` bash
apt update && apt upgrade -y
apt install -y ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu noble stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

docker version
docker compose version
```

## 5. Create appuser

``` bash
adduser --disabled-password --gecos "" appuser
# Add to docker group so user can manage Docker without sudo
usermod -aG docker appuser
# exit and reconnect as appuser
exit
ssh appuser@your_droplet_ip
```

## 6. Clone App from GitHub

``` bash
cd ~/
git clone https://github.com/Termondt-Tech/syvrona-ai.git
cd syvrona-ai
```

## 7. Upload .env to Droplet

``` bash
scp .env appuser@your_droplet_ip:/home/appuser/syvrona-ai/
```

Ensure your app uses:

``` bash
from dotenv import load_dotenv
load_dotenv('.env')
```

## 8. Confirm Docker Setup

### docker-compose.yml

``` bash
version: '3.9'
services:
  web:
    build: .
    ports:
1. "5001:5000"
    volumes:
1. .:/app
1. sqlite_data:/app/instance
    environment:
1. FLASK_APP=app.py
1. FLASK_ENV=development
1. FLASK_RUN_HOST=0.0.0.0
1. FLASK_RUN_PORT=5000
1. OPENAI_API_KEY
volumes:
  sqlite_data:
```

### Dockerfile

``` bash
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

## 9. Build and Run

``` bash
docker compose up -d --build
```

## 10. Initialize MySQL DB

``` bash
docker exec -it <container_name> /bin/sh
python create_database.py
exit
```

## 11. Configure Firewall

``` bash
ufw allow OpenSSH
ufw allow 5001
ufw allow 80
ufw allow 443
ufw enable
ufw reload
```

## 12. Install and Configure Caddy

### Install Caddy

``` bash
apt install -y debian-keyring debian-archive-keyring curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy
```

### Edit Caddyfile

``` bash
nano /etc/caddy/Caddyfile
```

**Replace contents with:**

``` bash
syvrona.com, www.syvrona.com {
    reverse_proxy localhost:5001
}
```

**Replace contents with to support maintenance mode:**

``` bash
syvrona.com, www.syvrona.com {
    @maintenance {
        file {
            try_files /srv/maintenance/enabled
        }
    }
    handle @maintenance {
        root * /srv/maintenance
        file_server
        try_files {path} /index.html
    }
    handle {
        reverse_proxy localhost:5001
    }
}
```

### Reload Caddy

``` bash
systemctl reload caddy
```

## 13. Configure DNS in Namecheap

In ''Advanced DNS'' tab, create:
^ Type ^ Host ^ Value ^ TTL ^

| A | @ | your_droplet_ip | Automatic |
| --- | --- | --- | --- |
| A | www | your_droplet_ip | Automatic |

Wait 15–60 minutes for propagation.

## 14. Verify Everything Works

Go to:

* <https://syvrona.com>

You should see your app with a valid SSL certificate.

**✅ Success!** Your Flask app is now:

* Running in Docker
* Hosted on DigitalOcean
* Secured with HTTPS (Caddy + Let’s Encrypt)
* Served via your custom domain
