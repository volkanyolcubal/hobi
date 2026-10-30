# -*- coding: utf-8 -*-
"""
Sahte 'ollama' modülü.
Ana Aura dosyasının yanına koyulunca 'import ollama' ve
'from ollama import Client, generate' gerçek Ollama yerine
yerel GGUF motoruna (aura_yerel_motor.py) gider.
Ana kodda hiçbir değişiklik gerekmez.
"""
from aura_yerel_motor import LocalClient, Client  # noqa: F401

_varsayilan = LocalClient()


def chat(*args, **kwargs):
    return _varsayilan.chat(*args, **kwargs)


def generate(*args, **kwargs):
    return _varsayilan.generate(*args, **kwargs)


def list():  # noqa: A001
    return _varsayilan.list()
