@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Installation des bibliotheques Python necessaires...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo pyreadstat non installe (bibliotheque facultative) : installation des autres.
  python -m pip install pandas openpyxl matplotlib
)
echo.
echo Installation terminee. Lancez LANCER_APPLICATION.bat
pause
