# Project Commands

## Virtual Environment
### Create
python -m venv venv

### Activate (Windows)
venv\Scripts\activate.bat

### Activate (Mac/Linux)
source venv/bin/activate

## Dependency Management
### Install requirements
pip install -r requirements.txt

### Freeze requirements
pip freeze > requirements.txt

## Git Workflow
### Initialize and Link
git init
git remote add origin https://github.com/46-akshat/ShopWave-AutoResolver.git

### Handling Updates & Initial Push
# Use this if GitHub has files (README/License) you don't have locally
git pull origin main --rebase

# Stage and Commit
git add .
git commit -m "feat: complete LangGraph reasoning engine with policy guardrails"

# Push to Main
git branch -M main
git push -u origin main

