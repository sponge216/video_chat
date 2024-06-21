@echo off
SET VAR=%cd%

py -m ensurepip --upgrade
pip install -r %VAR%\requirements.txt
