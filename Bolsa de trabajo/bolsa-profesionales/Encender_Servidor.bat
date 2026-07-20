@echo off
title Iniciando Servidor TalentPool
echo Levantando el servidor de Python...
py -m uvicorn main:app --reload
pause