# Running familyman on Raspberry Pi

This guide explains how to set up and run familyman on a Raspberry Pi, tested on aarch64 (64-bit) systems running Debian-based distributions like MainsailOS.

## Prerequisites

### Hardware
- Raspberry Pi 4 or newer (recommended for face recognition processing)
- At least 4GB RAM (8GB recommended for face clustering)
- SD card with at least 16GB storage
- Network connection (WiFi or Ethernet)

### System Requirements
- Debian-based OS (Raspberry Pi OS, MainsailOS, etc.)
- Python 3.8 or newer
- Sufficient storage for your photo library

## Installation

### 1. System Dependencies

First, update your system and install required packages:

```bash
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    exiftool \
    cmake \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    libatlas-base-dev \
    libhdf5-dev
```

### 2. Install dlib for ARM

The `face-recognition` library requires `dlib`, which needs to be built from source on ARM architectures. This process can take 30-60 minutes on a Raspberry Pi.

```bash
# Install dlib with optimizations for ARM
pip3 install --no-cache-dir dlib
```

**Note**: If you encounter compilation issues, you can try building dlib with reduced optimizations:

```bash
# Alternative: build with fewer optimizations (faster but less accurate)
pip3 install --no-cache-dir --no-binary :all: dlib
```

### 3. Clone the Repository

```bash
cd ~
git clone https://github.com/ap0ught/familyman.git
cd familyman
```

### 4. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 5. Install Python Dependencies

```bash
# Install the main requirements
pip install -r requirements.txt
```

If you encounter issues with face-recognition on ARM, try installing dependencies one by one:

```bash
pip install Django Pillow djangorestframework numpy scikit-learn
pip install face-recognition
```

### 6. Configure Django

Set environment variables for network access:

```bash
# Allow access from your local network
export FAMILYMAN_ALLOWED_HOSTS="*"
# Or specify your Pi's IP address
export FAMILYMAN_ALLOWED_HOSTS="192.168.86.215,localhost,127.0.0.1"

# Set a secure secret key for production
export FAMILYMAN_SECRET="your-secure-random-secret-key-here"
```

To make these permanent, add them to your `~/.bashrc` or create a `.env` file:

```bash
# Add to ~/.bashrc for automatic loading
echo 'export FAMILYMAN_ALLOWED_HOSTS="*"' >> ~/.bashrc
echo 'export FAMILYMAN_SECRET="your-secret-key"' >> ~/.bashrc
source ~/.bashrc
```

Or create a `.env` file (without `export` keyword) and source it manually:

```bash
cat > .env <<EOF
FAMILYMAN_ALLOWED_HOSTS="*"
FAMILYMAN_SECRET="your-secure-random-secret-key-here"
EOF

# Load the environment variables
set -a
source .env
set +a
```

**Note**: The `setup_pi.sh` script automatically creates a `.env` file with a generated secret key.

### 7. Initialize Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

## Running the Application

### Development Server

To run on the default port (8000) accessible from your network:

```bash
# Allow access from any IP on your network
python manage.py runserver 0.0.0.0:8000
```

Access the application at: `http://192.168.86.215:8000` (replace with your Pi's IP address)

### Production Deployment

For production use, consider using a proper WSGI server:

#### Using Gunicorn

```bash
pip install gunicorn

# Run with 2 workers (adjust based on your Pi's RAM)
gunicorn --workers 2 --bind 0.0.0.0:8000 familyman_site.wsgi:application
```

#### Using systemd Service

Create a systemd service file at `/etc/systemd/system/familyman.service`:

```ini
[Unit]
Description=FamilyMan Photo Manager
After=network.target

[Service]
# NOTE: Customize User, Group, and WorkingDirectory paths to match your installation
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/familyman
# SECURITY WARNING: Change these defaults before deploying to production!
# - Set FAMILYMAN_ALLOWED_HOSTS to specific IPs/domains instead of "*"
# - Generate a secure FAMILYMAN_SECRET with: python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
# - Ensure DEBUG=False in production (set via environment or modify settings.py)
Environment="FAMILYMAN_ALLOWED_HOSTS=localhost,127.0.0.1"
Environment="FAMILYMAN_SECRET=your-secret-key"
ExecStart=/home/pi/familyman/.venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:8000 \
    --timeout 60 \
    familyman_site.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable familyman
sudo systemctl start familyman
sudo systemctl status familyman
```

## Performance Tips for Raspberry Pi

### Face Recognition Optimization

Face recognition and clustering can be CPU-intensive on a Raspberry Pi. Consider these optimizations:

1. **Process photos in smaller batches**:
   ```bash
   # Process a subset of photos at a time
   python3 face_cluster_and_tag.py /path/to/photos --limit 100
   ```

2. **Reduce image resolution**: The face recognition library works better with smaller images on resource-constrained devices.

3. **Run face clustering during off-hours**: Schedule intensive tasks when the Pi isn't being actively used.

4. **Use swap space**: Ensure you have adequate swap configured:
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=2048 or higher
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

### Memory Management

- Close unnecessary applications before running face clustering
- Monitor system resources: `htop` or `top`
- Consider using lightweight alternatives to the Django dev server for production

## Troubleshooting

### dlib Installation Fails

If dlib fails to build, ensure you have all dependencies:
```bash
sudo apt-get install -y cmake build-essential libopenblas-dev liblapack-dev
```

### Out of Memory During Face Recognition

- Reduce the number of photos processed at once
- Increase swap space (see Performance Tips above)
- Consider using a Pi with more RAM (8GB model recommended)

### Cannot Access from Network

1. Check firewall settings:
   ```bash
   sudo ufw status
   # If firewall is active, allow port 8000
   sudo ufw allow 8000
   ```

2. Verify `FAMILYMAN_ALLOWED_HOSTS` is set correctly

3. Ensure the server is bound to `0.0.0.0` not just `127.0.0.1`

### Slow Performance

- The first face recognition run will be slow as models are loaded
- Subsequent runs should be faster
- Consider using a Pi 4 or Pi 5 for better performance
- Use a fast SD card (Class 10, UHS-I or better) or USB 3.0 SSD

## Security Considerations

When running on a network-accessible Pi:

1. **Change the default secret key**:
   ```bash
   export FAMILYMAN_SECRET="$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
   ```

2. **Use a reverse proxy** (nginx) with HTTPS for production
3. **Restrict access** by setting specific IPs in `FAMILYMAN_ALLOWED_HOSTS`
4. **Keep your system updated**:
   ```bash
   sudo apt-get update && sudo apt-get upgrade
   ```

## Additional Resources

- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [dlib Installation Guide](http://dlib.net/compile.html)

## Support

For issues specific to Raspberry Pi deployment, please open an issue on GitHub with:
- Your Pi model and RAM
- OS version (`cat /etc/os-release`)
- Python version (`python3 --version`)
- Error messages or logs
