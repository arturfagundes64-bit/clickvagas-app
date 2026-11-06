import json
import os

import flet as ft

from parking_data import new_state

_STORAGE_KEY = "click_vagas_state_v1"


async def carregar_estado(preferencias):
    salvo = await preferencias.get(_STORAGE_KEY)
    if isinstance(salvo, str):
        try:
            estado = json.loads(salvo)
            if isinstance(estado, dict) and isinstance(estado.get("usuarios"), dict) and isinstance(estado.get("vagas"), list):
                return estado
        except json.JSONDecodeError:
            pass
    estado = new_state()
    await salvar_estado(preferencias, estado)
    return estado


async def salvar_estado(preferencias, estado):
    await preferencias.set(_STORAGE_KEY, json.dumps(estado, ensure_ascii=False))


class LocalStore:
    """Usa SQLite no app instalado e SharedPreferences no preview web."""

    def __init__(self):
        self.preferencias = None
        self.banco = None

    async def carregar(self, page):
        self.preferencias = ft.SharedPreferences()
        if page.web:
            return await carregar_estado(self.preferencias)

        # O caminho de suporte é gravável e privado para esta instalação do app.
        caminhos = ft.StoragePaths()
        pasta = await caminhos.get_application_support_directory()
        os.makedirs(pasta, exist_ok=True)
        from database import SQLiteDatabase

        self.banco = SQLiteDatabase(os.path.join(pasta, "click_vagas.sqlite3"))
        estado = self.banco.load_state()
        if estado is not None:
            return estado

        # Migra usuários e veículos da versão anterior, que usava SharedPreferences.
        salvo = await self.preferencias.get(_STORAGE_KEY)
        if isinstance(salvo, str):
            try:
                legado = json.loads(salvo)
            except json.JSONDecodeError:
                legado = None
        else:
            legado = None

        if not isinstance(legado, dict) or not isinstance(legado.get("usuarios"), dict) or not isinstance(legado.get("vagas"), list):
            legado = new_state()
        self.banco.save_state(legado)
        return self.banco.load_state()

    async def salvar(self, estado):
        if self.banco is not None:
            self.banco.save_state(estado)
        else:
            await salvar_estado(self.preferencias, estado)
