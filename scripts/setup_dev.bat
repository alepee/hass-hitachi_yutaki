@echo off
setlocal

REM Creating virtual environment if it doesn't exist
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activating virtual environment
call venv\Scripts\activate.bat

REM Installing development dependencies
python -m pip install --upgrade pip
pip install wheel
pip install -r requirements_dev.txt

REM Clone Home Assistant if it doesn't exist
if not exist core (
    echo Cloning Home Assistant...
    git clone https://github.com/home-assistant/core.git
)

REM Installing Home Assistant in development mode
cd core
pip install -e .
cd ..

REM Installing pre-commit hooks
pre-commit install

REM Creating dev configuration directory if needed
if not exist config\custom_components mkdir config\custom_components
mklink /D config\custom_components\hitachi_yutaki ..\..\custom_components\hitachi_yutaki

echo Development environment setup complete!
echo You can now run 'hass -c config' to start Home Assistant with your integration

endlocal
