#!/bin/bash

# Creating virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activating virtual environment
source venv/bin/activate

# Installing development dependencies
pip install --upgrade pip
pip install wheel
pip install -r requirements_dev.txt

# Clone Home Assistant if it doesn't exist
if [ ! -d "core" ]; then
    echo "Cloning Home Assistant..."
    git clone https://github.com/home-assistant/core.git
fi

# Installing Home Assistant in development mode
cd core
pip install -e .
cd ..

# Installing pre-commit hooks
pre-commit install

# Creating dev configuration directory if needed
mkdir -p config/custom_components
ln -s ../../custom_components/hitachi_yutaki config/custom_components/

echo "Development environment setup complete!"
echo "You can now run 'hass -c config' to start Home Assistant with your integration"
