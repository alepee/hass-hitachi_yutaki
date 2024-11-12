#!/bin/bash

# Création de l'environnement virtuel s'il n'existe pas
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activation de l'environnement virtuel
source venv/bin/activate

# Installation des dépendances de développement
pip install --upgrade pip
pip install wheel
pip install -r requirements_dev.txt

# Clone Home Assistant s'il n'existe pas déjà
if [ ! -d "core" ]; then
    echo "Cloning Home Assistant..."
    git clone https://github.com/home-assistant/core.git
fi

# Installation de Home Assistant en mode développement
cd core
pip install -e .
cd ..

# Installation des pre-commit hooks
pre-commit install

# Création du répertoire de configuration de dev si nécessaire
mkdir -p config/custom_components
ln -s ../../custom_components/hitachi_yutaki config/custom_components/

echo "Development environment setup complete!"
echo "You can now run 'hass -c config' to start Home Assistant with your integration"
