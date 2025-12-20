#!/usr/bin/env bash
#
# setup_pi.sh
# Helper script to set up familyman on Raspberry Pi
#
# Usage:
#   chmod +x setup_pi.sh
#   ./setup_pi.sh
#

set -e

echo "================================================"
echo "FamilyMan Raspberry Pi Setup Script"
echo "================================================"
echo ""

# Check if running on ARM architecture
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" ]] && [[ "$ARCH" != "armv7l" ]]; then
    echo "Warning: This script is designed for ARM architecture (aarch64/armv7l)."
    echo "Detected architecture: $ARCH"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for root/sudo
if [ "$EUID" -eq 0 ]; then
    echo "Please run this script as a normal user, not as root."
    echo "The script will prompt for sudo password when needed."
    exit 1
fi

echo "Step 1: Installing system dependencies..."
echo "This will require sudo privileges."
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
    libhdf5-dev || {
        echo "Error: Failed to install system dependencies"
        exit 1
    }

echo ""
echo "Step 2: Creating Python virtual environment..."
if [ -d ".venv" ]; then
    echo "Virtual environment already exists. Skipping creation."
else
    python3 -m venv .venv || {
        echo "Error: Failed to create virtual environment"
        exit 1
    }
fi

echo ""
echo "Step 3: Activating virtual environment..."
source .venv/bin/activate || {
    echo "Error: Failed to activate virtual environment"
    exit 1
}

echo ""
echo "Step 4: Upgrading pip..."
pip install --upgrade pip setuptools wheel

echo ""
echo "Step 5: Installing Python dependencies..."
echo "Note: Installing dlib can take 30-60 minutes on Raspberry Pi."
echo "Please be patient..."

# Install dependencies one by one for better error handling
pip install Django Pillow djangorestframework numpy scikit-learn || {
    echo "Error: Failed to install basic Python dependencies"
    exit 1
}

echo ""
echo "Installing face-recognition (this may take a while)..."
pip install face-recognition || {
    echo "Warning: face-recognition installation failed."
    echo "You can try installing it manually later with:"
    echo "  source .venv/bin/activate"
    echo "  pip install face-recognition"
}

echo ""
echo "Step 6: Setting up environment variables..."
if [ -f ".env" ]; then
    echo ".env file already exists. Skipping creation."
else
    cat > .env <<EOF
# FamilyMan Environment Configuration for Raspberry Pi
# Uncomment and modify as needed

# Allow access from network (use * for all, or specify IPs)
export FAMILYMAN_ALLOWED_HOSTS="*"

# Generate a secure secret key for production
# You can generate one with: python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
export FAMILYMAN_SECRET="change-me-in-production"

# Optional: Set media root for photos
# export MEDIA_ROOT="/path/to/your/photos"
EOF
    echo "Created .env file. Please review and update it with secure values."
fi

echo ""
echo "Step 7: Initializing database..."
source .env 2>/dev/null || true
python manage.py migrate || {
    echo "Error: Database migration failed"
    exit 1
}

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Load environment variables:"
echo "   source .env"
echo ""
echo "2. Create a superuser for admin access:"
echo "   python manage.py createsuperuser"
echo ""
echo "3. Start the development server:"
echo "   python manage.py runserver 0.0.0.0:8000"
echo ""
echo "4. Access the application from your network:"
echo "   http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "For production deployment, see README-pi.md"
echo ""
echo "To activate the virtual environment in future sessions:"
echo "   cd $(pwd)"
echo "   source .venv/bin/activate"
echo "   source .env"
echo ""
