@echo off
setlocal

REM Création de l'environnement virtuel s'il n'existe pas
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activation de l'environnement virtuel
call venv\Scripts\activate.bat

REM Installation des dépendances de développement
python -m pip install --upgrade pip
pip install wheel
pip install -r requirements_dev.txt

REM Clone Home Assistant s'il n'existe pas déjà
if not exist core (
    echo Cloning Home Assistant...
    git clone https://github.com/home-assistant/core.git
)

REM Installation de Home Assistant en mode développement
cd core
pip install -e .
cd ..

REM Installation des pre-commit hooks
pre-commit install

REM Création du répertoire de configuration de dev si nécessaire
if not exist config\custom_components mkdir config\custom_components
mklink /D config\custom_components\hitachi_yutaki ..\..\custom_components\hitachi_yutaki

echo Development environment setup complete!
echo You can now run 'hass -c config' to start Home Assistant with your integration

endlocal
