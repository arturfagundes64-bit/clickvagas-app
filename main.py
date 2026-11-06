import math
import re
from datetime import datetime

import flet as ft
import flet_charts as fch
import qrcode

from auth import hash_password, verify_password
from parking_data import calcular_tarifa
from storage import LocalStore

# Cores da marca fornecidas no código original; não há correspondência exata
# para estes dois tons personalizados na paleta ft.Colors.
AZUL = "#0a2540"
LARANJA = "#ff6b35"


class ClickVagasApp:
    def __init__(self, page: ft.Page, store, estado):
        self.page = page
        self.store = store
        self.estado = estado
        self.usuario_logado = None
        self.indice = 0
        self.filtro_veiculo = "carro"
        self.estado.setdefault("eventos", [])
        for vaga in self.estado.get("vagas", []):
            tipo_existente = vaga.get("tipo_vaga")
            if tipo_existente not in ("carro", "moto"):
                tipo_existente = (
                    vaga.get("tipo_veiculo", "carro")
                    if vaga.get("status") == "ocupado"
                    else "carro"
                )
            vaga["tipo_vaga"] = tipo_existente
            if vaga.get("status") == "ocupado":
                vaga.setdefault("tipo_veiculo", tipo_existente)
                entrada = vaga.get("entrada")
                ja_registrada = any(
                    evento.get("tipo") == "entrada"
                    and evento.get("vaga") == vaga.get("numero")
                    and evento.get("horario") == entrada
                    for evento in self.estado["eventos"]
                )
                if entrada and not ja_registrada:
                    self.estado["eventos"].append({
                        "tipo": "entrada", "vaga": vaga.get("numero"),
                        "usuario": vaga.get("usuario") or "",
                        "modelo": vaga.get("modelo") or "",
                        "placa": vaga.get("placa") or "",
                        "tipo_veiculo": vaga.get("tipo_veiculo") or "carro",
                        "horario": entrada, "valor": 0.0,
                    })
        self.login_nome = ft.TextField(label="Nome de usuário", width=280, autofocus=True)
        self.login_senha = ft.TextField(label="Senha", width=280, password=True, can_reveal_password=True)
        self.cad_nome = ft.TextField(label="Nome de usuário", width=280)
        self.cad_email = ft.TextField(label="E-mail", width=280, keyboard_type=ft.KeyboardType.EMAIL)
        self.cad_telefone = ft.TextField(label="Telefone", width=280, keyboard_type=ft.KeyboardType.PHONE)
        self.cad_senha = ft.TextField(label="Senha", width=280, password=True, can_reveal_password=True)
        self.cad_confirmar = ft.TextField(label="Confirmar senha", width=280, password=True, can_reveal_password=True)
        for usuario in self.estado.get("usuarios", {}).values():
            usuario.setdefault("email", "")
            usuario.setdefault("telefone", "")
            usuario.setdefault("veiculos", [])
            for veiculo in usuario["veiculos"]:
                veiculo.setdefault("tipo_veiculo", "carro")
        self.rec_nome = ft.TextField(label="Nome de usuário", width=280)
        self.rec_senha = ft.TextField(label="Nova senha", width=280, password=True, can_reveal_password=True)
        self.rec_confirmar = ft.TextField(label="Confirmar nova senha", width=280, password=True, can_reveal_password=True)

    async def persistir(self):
        await self.store.salvar(self.estado)

    def mensagem(self, texto):
        self.page.show_dialog(ft.SnackBar(content=ft.Text(texto)))

    def botao_pill(self, texto, callback, cor=AZUL, largura=None):
        return ft.Container(
            width=largura,
            height=46,
            padding=ft.Padding(20, 0, 20, 0),
            border_radius=23,
            bgcolor=cor,
            ink=True,
            alignment=ft.Alignment.CENTER,
            on_click=callback,
            content=ft.Text(texto, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
        )

    def logo_tile(self, tamanho=150):
        return ft.Container(
            width=tamanho,
            height=tamanho,
            border_radius=ft.BorderRadius.all(min(28, tamanho * 0.2)),
            bgcolor=ft.Colors.WHITE,
            shadow=ft.BoxShadow(
                blur_radius=14 if tamanho > 80 else 4,
                spread_radius=2 if tamanho > 80 else 1,
                color=ft.Colors.BLUE_GREY_100,
                offset=ft.Offset(0, 3),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            alignment=ft.Alignment.CENTER,
            content=ft.Image(
                src="logoCV.png",
                width=tamanho,
                height=tamanho,
                fit=ft.BoxFit.COVER,
            ),
        )

    def mostrar_login(self):
        self.page.clean()
        self.page.appbar = None
        self.page.navigation_bar = None
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.login_nome.error = None
        self.login_senha.error = None
        self.page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        self.logo_tile(150),
                        ft.Text("Click Vagas", size=30, weight=ft.FontWeight.BOLD, color=AZUL),
                        ft.Text("Gestão simples para o seu estacionamento", text_align=ft.TextAlign.CENTER, size=13),
                        self.login_nome,
                        self.login_senha,
                        self.botao_pill("Entrar", self.fazer_login, largura=280),
                        ft.TextButton(content=ft.Text("Esqueceu a senha?"), on_click=self.mostrar_recuperacao),
                        ft.TextButton(content=ft.Text("Criar uma conta"), on_click=self.mostrar_cadastro),
                    ],
                )
            )
        )

    def mostrar_recuperacao(self):
        self.page.clean()
        for campo in (self.rec_nome, self.rec_senha, self.rec_confirmar):
            campo.error = None
        self.page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        self.logo_tile(130),
                        ft.Text("Redefinir senha", size=27, weight=ft.FontWeight.BOLD, color=AZUL),
                        ft.Text(
                            "Redefina sua senha neste dispositivo, sem confirmação por e-mail.",
                            size=12,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.GREY_700,
                        ),
                        self.rec_nome,
                        self.rec_senha,
                        self.rec_confirmar,
                        self.botao_pill("Salvar nova senha", self.redefinir_senha, largura=280),
                        ft.TextButton(content=ft.Text("Voltar ao login"), on_click=self.mostrar_login),
                    ],
                ),
            )
        )

    async def redefinir_senha(self):
        nome = (self.rec_nome.value or "").strip()
        senha = self.rec_senha.value or ""
        confirmar = self.rec_confirmar.value or ""
        usuario = self.estado["usuarios"].get(nome)
        self.rec_nome.error = "Informe um nome de usuário" if not nome else None
        if nome and not usuario:
            self.rec_nome.error = "Não encontramos essa conta neste dispositivo."
        self.rec_senha.error = "Informe a nova senha" if not senha else None
        self.rec_confirmar.error = "As senhas não coincidem" if confirmar != senha else None
        self.page.update()
        if any(campo.error for campo in (self.rec_nome, self.rec_senha, self.rec_confirmar)):
            return
        usuario["senha"] = hash_password(senha)
        await self.persistir()
        self.login_nome.value = nome
        self.login_senha.value = ""
        self.mostrar_login()
        self.mensagem("Senha atualizada neste dispositivo.")

    async def fazer_login(self, e):
        nome = (self.login_nome.value or "").strip()
        senha = self.login_senha.value or ""
        usuario = self.estado["usuarios"].get(nome)
        self.login_nome.error = "Informe seu nome de usuário." if not nome else None
        self.login_senha.error = "Informe sua senha." if not senha else None
        if nome and senha and (not usuario or not verify_password(senha, usuario.get("senha", ""))):
            self.login_senha.error = "Nome de usuário ou senha inválidos."
        self.page.update()
        if self.login_nome.error or self.login_senha.error:
            return
        self.usuario_logado = nome
        self.indice = 0
        self.renderizar()

    def mostrar_cadastro(self, e=None):
        self.page.clean()
        for campo in (self.cad_nome, self.cad_email, self.cad_telefone, self.cad_senha, self.cad_confirmar):
            campo.error = None
        self.page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        self.logo_tile(110),
                        ft.Text("Criar conta", size=27, weight=ft.FontWeight.BOLD, color=AZUL),
                        self.cad_nome,
                        self.cad_email,
                        self.cad_telefone,
                        self.cad_senha,
                        self.cad_confirmar,
                        self.botao_pill("Cadastrar", self.cadastrar_usuario, largura=280),
                        ft.TextButton(content=ft.Text("Já tenho conta · Entrar"), on_click=self.mostrar_login),
                    ],
                )
            )
        )

    async def cadastrar_usuario(self, e):
        nome = (self.cad_nome.value or "").strip()
        senha = self.cad_senha.value or ""
        confirmar = self.cad_confirmar.value or ""
        email = (self.cad_email.value or "").strip()
        telefone = (self.cad_telefone.value or "").strip()
        self.cad_nome.error = "Informe um nome de usuário" if not nome else None
        if nome and nome in self.estado["usuarios"]:
            self.cad_nome.error = "Este nome de usuário já está em uso."
        self.cad_email.error = "Informe um e-mail válido" if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) else None
        self.cad_telefone.error = None
        self.cad_senha.error = "Informe uma senha" if not senha else None
        self.cad_confirmar.error = "As senhas não coincidem" if confirmar != senha else None
        self.page.update()
        if any(campo.error for campo in (self.cad_nome, self.cad_email, self.cad_senha, self.cad_confirmar)):
            return
        self.estado["usuarios"][nome] = {
            "senha": hash_password(senha), "tipo": "cliente", "email": email,
            "telefone": telefone, "veiculos": []
        }
        await self.persistir()
        self.login_nome.value = nome
        self.login_senha.value = ""
        self.mostrar_login()

    def ir_para(self, indice):
        if indice == 2 and not self.eh_admin():
            return
        self.indice = indice
        self.renderizar()

    def eh_admin(self):
        usuario = self.estado["usuarios"].get(self.usuario_logado or "", {})
        return usuario.get("tipo") == "admin"

    def renderizar(self):
        if not self.usuario_logado:
            self.mostrar_login()
            return
        telas = [self.view_inicio, self.view_vagas, self.view_relatorio, self.view_sobre, self.view_perfil]
        cabecalho = self.criar_cabecalho()
        self.page.clean()
        self.page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        self.page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[cabecalho, telas[self.indice]()],
                ),
            )
        )

    def criar_cabecalho(self):
        itens = [("Início", 0), ("Vagas", 1)]
        if self.eh_admin():
            itens.append(("Relatório", 2))
        itens.extend([("Sobre", 3), ("Perfil", 4)])
        menu = ft.Row(
            scroll=ft.ScrollMode.AUTO,
            spacing=2,
            controls=[
                ft.TextButton(
                    content=ft.Text(rotulo, color=LARANJA if self.indice == indice else ft.Colors.WHITE),
                    on_click=lambda e, i=indice: self.ir_para(i),
                )
                for rotulo, indice in itens
            ],
        )
        return ft.Container(
            bgcolor=AZUL,
            padding=ft.Padding(12, 8, 8, 8),
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        controls=[
                            self.logo_tile(38),
                            ft.Text("Click Vagas", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, expand=True),
                            ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", icon_color=ft.Colors.WHITE, on_click=self.sair),
                        ]
                    ),
                    menu,
                ],
            ),
        )

    def sair(self, e):
        self.usuario_logado = None
        self.mostrar_login()

    def view_inicio(self):
        vagas = self.estado["vagas"]
        livres = sum(v["status"] == "livre" for v in vagas)
        ocupadas = len(vagas) - livres
        taxa = ocupadas / len(vagas) if vagas else 0
        resumo = ft.Row(
            wrap=True,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            controls=[
                self.card_resumo("Vagas livres", livres, ft.Colors.GREEN_700),
                self.card_resumo("Vagas ocupadas", ocupadas, ft.Colors.RED_400),
            ],
        )
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                ft.Container(
                    margin=ft.Margin.all(14),
                    padding=ft.Padding(20, 22, 20, 22),
                    border_radius=14,
                    bgcolor=AZUL,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Text("Estacione com praticidade e segurança.", size=27, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text("Consulte as vagas e acompanhe a ocupação do estacionamento em tempo real.", size=14, color=ft.Colors.WHITE),
                            self.botao_pill("Ver vagas", lambda e: self.ir_para(1), LARANJA),
                        ],
                    ),
                ),
                ft.Text(f"Olá, {self.usuario_logado}!", size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Container(
                    padding=ft.Padding(18, 12, 18, 12),
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[ft.Text("Ocupação"), ft.Text(f"{int(taxa * 100)}%", weight=ft.FontWeight.BOLD)],
                            ),
                            ft.ProgressBar(value=taxa, color=LARANJA, bgcolor=ft.Colors.GREY_300),
                        ]
                    ),
                ),
                resumo,
                ft.Container(height=12),
            ],
        )

    def card_resumo(self, titulo, valor, cor):
        return ft.Card(
            content=ft.Container(
                width=145,
                padding=16,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(str(valor), size=30, weight=ft.FontWeight.BOLD, color=cor),
                        ft.Text(titulo, size=13, text_align=ft.TextAlign.CENTER),
                    ],
                ),
            )
        )

    def view_vagas(self):
        lista = [
            vaga for vaga in self.estado["vagas"]
            if vaga.get("tipo_vaga", "carro") == self.filtro_veiculo
        ]
        return ft.Column(
            expand=True,
            controls=[
                ft.Container(
                    padding=ft.Padding(12, 10, 12, 0),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.SegmentedButton(
                                selected=[self.filtro_veiculo],
                                segments=[
                                    ft.Segment(value="carro", label="Carros"),
                                    ft.Segment(value="moto", label="Motos"),
                                ],
                                on_change=self.mudar_filtro,
                            )
                        ],
                    ),
                ),
                ft.ListView(expand=True, spacing=8, padding=12, controls=[self.card_vaga(v) for v in lista]),
            ],
        )

    def mudar_filtro(self, e):
        if e.control.selected:
            self.filtro_veiculo = e.control.selected[0]
            self.renderizar()

    def card_vaga(self, vaga):
        ocupada = vaga["status"] == "ocupado"
        itens = [
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(f"Vaga {vaga['numero']}", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Ocupada" if ocupada else "Livre", color=ft.Colors.RED_600 if ocupada else ft.Colors.GREEN_700),
                ],
            )
        ]
        if ocupada:
            tempo, valor = calcular_tarifa(vaga.get("entrada"))
            itens.extend([
                ft.Text(
                    f"{('Moto' if vaga.get('tipo_veiculo') == 'moto' else 'Carro')} · "
                    f"{vaga.get('modelo', '-')} · {vaga.get('placa', '-')}"
                ),
                ft.Text(f"{tempo} · R$ {valor:.2f}", size=13, color=ft.Colors.GREY_700),
                ft.TextButton(content=ft.Text("Liberar vaga"), on_click=lambda e, n=vaga["numero"]: self.liberar_vaga(n)),
            ])
        else:
            itens.append(ft.TextButton(content=ft.Text("Cadastrar veículo"), on_click=lambda e, n=vaga["numero"]: self.abrir_cadastro_veiculo(n)))
        return ft.Card(content=ft.Container(padding=14, content=ft.Column(spacing=6, controls=itens)))

    def abrir_cadastro_veiculo(self, numero=None):
        livres = [v for v in self.estado["vagas"] if v["status"] == "livre"]
        if not livres:
            self.mensagem("Não há vagas livres no momento.")
            return
        modelo = ft.TextField(label="Modelo do veículo", autofocus=True)
        placa = ft.TextField(label="Placa")
        vaga_selecionada = next(
            (v for v in self.estado["vagas"] if v["numero"] == numero), None
        ) if numero is not None else None
        tipo_inicial = (
            vaga_selecionada.get("tipo_vaga", "carro")
            if vaga_selecionada else self.filtro_veiculo
        )
        tipo_veiculo = ft.Dropdown(
            label="Tipo de veículo",
            value=tipo_inicial,
            disabled=vaga_selecionada is not None,
            options=[
                ft.DropdownOption(key="carro", text="Carro"),
                ft.DropdownOption(key="moto", text="Moto"),
            ],
        )
        dropdown = None
        if numero is None:
            def opcoes_livres(tipo):
                return [
                    ft.DropdownOption(key=str(v["numero"]), text=f"Vaga {v['numero']}")
                    for v in livres
                    if v.get("tipo_vaga", "carro") == tipo
                ]

            dropdown = ft.Dropdown(
                label="Escolha uma vaga livre",
                options=opcoes_livres(tipo_inicial),
            )

            def atualizar_opcoes_vagas(e):
                dropdown.options = opcoes_livres(e.control.value)
                dropdown.value = None
                dropdown.error_text = None
                self.page.update()

            tipo_veiculo.on_select = atualizar_opcoes_vagas
            controles = [tipo_veiculo, dropdown, modelo, placa]
        else:
            controles = [
                ft.Text(f"Vaga selecionada: {numero}", weight=ft.FontWeight.BOLD),
                tipo_veiculo, modelo, placa,
            ]

        async def confirmar(e):
            num = numero
            if num is None:
                if not dropdown.value:
                    dropdown.error_text = "Selecione uma vaga livre para esse tipo de veículo"
                    self.page.update()
                    return
                num = int(dropdown.value)
            placa_texto = (placa.value or "").strip().upper()
            padrao = r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$|^[A-Z]{3}-?[0-9]{4}$"
            modelo.error = None if (modelo.value or "").strip() else "Informe o modelo"
            duplicada = any(
                v.get("placa") == placa_texto and v["status"] == "ocupado"
                for v in self.estado["vagas"]
            )
            placa_invalida = not re.match(padrao, placa_texto) or duplicada
            placa.error = "Informe a placa" if not placa_texto else ("Placa inválida" if placa_invalida else None)
            self.page.update()
            if modelo.error or placa.error:
                return
            vaga = next((v for v in self.estado["vagas"] if v["numero"] == num), None)
            if not vaga or vaga["status"] != "livre":
                self.mensagem("Essa vaga não está mais livre. Atualize a lista e tente novamente.")
                self.page.pop_dialog()
                return
            if vaga.get("tipo_vaga", "carro") != tipo_veiculo.value:
                self.mensagem("O tipo de veículo não corresponde ao tipo da vaga selecionada.")
                return
            modelo_texto = modelo.value.strip()
            agora = datetime.now().isoformat()
            vaga.update({
                "status": "ocupado", "modelo": modelo_texto, "placa": placa_texto,
                "usuario": self.usuario_logado, "entrada": agora,
                "tipo_veiculo": tipo_veiculo.value,
            })
            self.estado["usuarios"][self.usuario_logado]["veiculos"].append({
                "modelo": modelo_texto, "placa": placa_texto, "vaga": num,
                "tipo_veiculo": tipo_veiculo.value,
            })
            self.estado["eventos"].append({
                "tipo": "entrada", "vaga": num, "usuario": self.usuario_logado,
                "modelo": modelo_texto, "placa": placa_texto,
                "tipo_veiculo": tipo_veiculo.value, "horario": agora, "valor": 0.0,
            })
            await self.persistir()
            self.page.pop_dialog()
            self.renderizar()

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Cadastrar veículo"),
                content=ft.Column(tight=True, spacing=10, controls=controles),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=lambda e: self.page.pop_dialog()),
                    ft.Button(content=ft.Text("Salvar"), on_click=confirmar),
                ],
            )
        )

    def liberar_vaga(self, numero):
        vaga = next(v for v in self.estado["vagas"] if v["numero"] == numero)
        if not self.eh_admin() and vaga.get("usuario") != self.usuario_logado:
            self.mensagem("Apenas o gestor ou a pessoa responsável pelo veículo pode liberar esta vaga.")
            return
        tempo, valor = calcular_tarifa(vaga.get("entrada"))
        forma_pagamento = ft.Dropdown(
            label="Forma de pagamento",
            value="pix",
            options=[
                ft.DropdownOption(key="pix", text="Pix"),
                ft.DropdownOption(key="cartao", text="Cartão no caixa"),
            ],
        )

        async def continuar(e):
            if forma_pagamento.value == "pix":
                self.abrir_pix(numero, valor)
            else:
                await self.registrar_saida(numero, valor, "Cartão no caixa")

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Liberar Vaga {numero}"),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(f"Veículo: {vaga.get('modelo')} ({vaga.get('placa')})"),
                        ft.Text(f"Tempo de permanência: {tempo}"),
                        ft.Text(f"Valor total: R$ {valor:.2f}", weight=ft.FontWeight.BOLD, color=AZUL),
                        forma_pagamento,
                    ],
                ),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=lambda e: self.page.pop_dialog()),
                    ft.Button(content=ft.Text("Continuar"), bgcolor=LARANJA, on_click=continuar),
                ],
            )
        )

    async def registrar_saida(self, numero, valor, forma_pagamento):
        vaga = next((v for v in self.estado["vagas"] if v["numero"] == numero), None)
        if not vaga or vaga.get("status") != "ocupado":
            self.page.pop_dialog()
            self.mensagem("Esta vaga já foi liberada.")
            return
        dono = vaga.get("usuario")
        if dono in self.estado["usuarios"]:
            usuario = self.estado["usuarios"][dono]
            usuario["veiculos"] = [v for v in usuario.get("veiculos", []) if v.get("vaga") != numero]
        self.estado["eventos"].append({
            "tipo": "saida", "vaga": numero, "usuario": dono or "",
            "modelo": vaga.get("modelo") or "", "placa": vaga.get("placa") or "",
            "tipo_veiculo": vaga.get("tipo_veiculo") or "carro",
            "horario": datetime.now().isoformat(), "valor": float(valor),
            "forma_pagamento": forma_pagamento,
        })
        vaga.update({
            "status": "livre", "modelo": None, "placa": None,
            "usuario": None, "entrada": None, "tipo_veiculo": None,
        })
        await self.persistir()
        self.page.pop_dialog()
        self.renderizar()
        self.mensagem(f"Pagamento registrado como {forma_pagamento}. Vaga {numero} liberada.")

    def abrir_pix(self, numero, valor):
        self.page.pop_dialog()
        codigo_pix = f"Click Vagas | Vaga {numero} | R$ {valor:.2f}"
        codigo = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
        codigo.add_data(codigo_pix)
        codigo.make(fit=True)
        matriz = codigo.get_matrix()
        modulo = max(3, min(5, 220 // len(matriz)))
        qr_visual = ft.Container(
            bgcolor=ft.Colors.WHITE,
            padding=8,
            content=ft.Column(
                tight=True,
                spacing=0,
                controls=[
                    ft.Row(
                        tight=True,
                        spacing=0,
                        controls=[
                            ft.Container(
                                width=modulo,
                                height=modulo,
                                bgcolor=ft.Colors.BLACK if escuro else ft.Colors.WHITE,
                            )
                            for escuro in linha
                        ],
                    )
                    for linha in matriz
                ],
            ),
        )

        async def copiar_codigo(e):
            try:
                await ft.Clipboard().set(codigo_pix)
                self.mensagem("Código Pix copiado.")
            except Exception:
                self.mensagem("Não foi possível copiar o código Pix.")

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Pagamento por Pix"),
                content=ft.Column(
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Text(f"Valor total: R$ {valor:.2f}", weight=ft.FontWeight.BOLD, color=AZUL),
                        qr_visual,
                        ft.TextField(value=codigo_pix, label="Código para copiar", read_only=True),
                        ft.TextButton(content=ft.Text("Copiar código"), on_click=copiar_codigo),
                    ],
                ),
                actions=[
                    ft.TextButton(content=ft.Text("Fechar"), on_click=lambda e: self.page.pop_dialog()),
                    ft.Button(
                        content=ft.Text("Confirmar pagamento e liberar"),
                        on_click=lambda e: self.registrar_saida(numero, valor, "Pix"),
                    ),
                ],
            )
        )

    def view_relatorio(self):
        ocupadas = [v for v in self.estado["vagas"] if v["status"] == "ocupado"]
        hoje = datetime.now().date()
        eventos_hoje = []
        for evento in self.estado.get("eventos", []):
            try:
                momento = datetime.fromisoformat(evento.get("horario", ""))
            except (TypeError, ValueError):
                continue
            if momento.date() == hoje:
                eventos_hoje.append((evento, momento))

        faixas = ["00–05", "06–11", "12–17", "18–23"]
        entradas = [0, 0, 0, 0]
        saidas = [0, 0, 0, 0]
        vendas = [0.0, 0.0, 0.0, 0.0]
        total_vendido = 0.0
        pagamentos = 0
        for evento, momento in eventos_hoje:
            faixa = min(momento.hour // 6, 3)
            if evento.get("tipo") == "entrada":
                entradas[faixa] += 1
            elif evento.get("tipo") == "saida":
                saidas[faixa] += 1
                valor = float(evento.get("valor", 0) or 0)
                vendas[faixa] += valor
                total_vendido += valor
                pagamentos += 1

        def criar_rotulos_faixas():
            return fch.ChartAxis(
                labels=[
                    fch.ChartAxisLabel(value=i, label=ft.Text(texto, size=13))
                    for i, texto in enumerate(faixas)
                ],
                label_size=48,
                show_min=False,
                show_max=False,
            )
        max_movimentos = max(entradas + saidas, default=0)
        grafico_movimentos = fch.BarChart(
            expand=True,
            groups=[
                fch.BarChartGroup(
                    x=i,
                    rods=[
                        fch.BarChartRod(to_y=entradas[i], width=20, color=AZUL, border_radius=ft.BorderRadius.all(16)),
                        fch.BarChartRod(to_y=saidas[i], width=20, color=LARANJA, border_radius=ft.BorderRadius.all(16)),
                    ],
                )
                for i in range(4)
            ],
            bottom_axis=criar_rotulos_faixas(),
            left_axis=fch.ChartAxis(show_labels=False, show_min=False, show_max=False),
            min_y=0,
            max_y=max(1, max_movimentos),
        )
        grafico_vendas = fch.BarChart(
            expand=True,
            groups=[
                fch.BarChartGroup(
                    x=i,
                    rods=[fch.BarChartRod(to_y=vendas[i], width=38, color=AZUL, border_radius=ft.BorderRadius.all(20))],
                )
                for i in range(4)
            ],
            bottom_axis=criar_rotulos_faixas(),
            left_axis=fch.ChartAxis(label_size=48),
            min_y=0,
            max_y=max(5, math.ceil(max(vendas, default=0.0) / 5) * 5),
        )

        itens = []
        for vaga in ocupadas:
            tempo, valor = calcular_tarifa(vaga.get("entrada"))
            entrada = datetime.fromisoformat(vaga["entrada"]).strftime("%H:%M") if vaga.get("entrada") else "-"
            itens.append(
                ft.Card(
                    content=ft.Container(
                        padding=12,
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(f"Vaga {vaga['numero']} · {vaga.get('modelo', '-')}", weight=ft.FontWeight.BOLD),
                                ft.Text(f"Placa: {vaga.get('placa', '-')} · Entrada: {entrada}"),
                                ft.Text(f"{tempo} · R$ {valor:.2f}", color=AZUL),
                            ],
                        ),
                    )
                )
            )
        if not itens:
            itens = [ft.Text("Nenhum veículo estacionado no momento.")]

        def card_relatorio(titulo, valor, cor, largura):
            return ft.Card(
                content=ft.Container(
                    width=largura,
                    padding=16,
                    content=ft.Column(
                        tight=True,
                        spacing=2,
                        controls=[
                            ft.Text(titulo, size=14, color=ft.Colors.GREY_700),
                            ft.Text(str(valor), size=28, weight=ft.FontWeight.BOLD, color=cor),
                        ],
                    ),
                )
            )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Container(
                    padding=16,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Text("Relatório diário", size=22, weight=ft.FontWeight.BOLD, color=AZUL),
                            ft.Text(f"Hoje · {hoje.strftime('%d/%m/%Y')}", color=ft.Colors.GREY_700),
                            ft.Text("Movimentação de veículos", size=18, weight=ft.FontWeight.BOLD),
                            ft.Row(
                                wrap=True,
                                spacing=12,
                                controls=[
                                    card_relatorio("Entradas", sum(entradas), AZUL, 112),
                                    card_relatorio("Saídas", sum(saidas), LARANJA, 112),
                                ],
                            ),
                            ft.Row(
                                spacing=16,
                                controls=[
                                    ft.Row(tight=True, spacing=6, controls=[ft.Container(width=14, height=14, bgcolor=AZUL), ft.Text("Entradas")]),
                                    ft.Row(tight=True, spacing=6, controls=[ft.Container(width=14, height=14, bgcolor=LARANJA), ft.Text("Saídas")]),
                                ],
                            ),
                            ft.Container(height=300, content=grafico_movimentos),
                            ft.Divider(color=ft.Colors.GREY_300),
                            ft.Text("Vendas do dia", size=18, weight=ft.FontWeight.BOLD),
                            ft.Row(
                                wrap=True,
                                spacing=12,
                                controls=[
                                    card_relatorio("Total recebido", f"R$ {total_vendido:.2f}", AZUL, 152),
                                    card_relatorio("Pagamentos", pagamentos, LARANJA, 128),
                                ],
                            ),
                            ft.Text("Vendas por faixa de horário", size=14, color=ft.Colors.GREY_700),
                            ft.Container(height=300, content=grafico_vendas),
                            ft.Divider(color=ft.Colors.GREY_300),
                            ft.Text("Veículos atualmente no estacionamento", size=18, weight=ft.FontWeight.BOLD),
                            *itens,
                        ],
                    ),
                ),
            ],
        )

    def view_sobre(self):
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(height=16),
                self.logo_tile(150),
                ft.Text("Click Vagas", size=27, color=AZUL, weight=ft.FontWeight.BOLD),
                ft.Card(content=ft.Container(width=330, padding=16, content=ft.Column(controls=[
                    ft.Text("Sobre o sistema", size=17, weight=ft.FontWeight.BOLD, color=AZUL),
                    ft.Text("Uma solução prática para acompanhar a ocupação, registrar veículos e consultar informações do estacionamento."),
                ]))),
                ft.Card(content=ft.Container(width=330, padding=16, content=ft.Column(controls=[
                    ft.Text("Recursos", size=17, weight=ft.FontWeight.BOLD, color=AZUL),
                    ft.Text("• Cadastro e liberação de vagas\n• Perfil com veículos\n• Relatório gerencial para gestores"),
                ]))),
            ],
        )

    def solicitar_exclusao_perfil(self, nome_usuario):
        usuario = self.estado["usuarios"].get(nome_usuario)
        if usuario is None:
            self.mensagem("Este perfil não foi encontrado.")
            return
        eh_proprio_perfil = nome_usuario == self.usuario_logado
        if not eh_proprio_perfil and not self.eh_admin():
            self.mensagem("Somente um administrador pode excluir outros perfis.")
            return
        if any(
            vaga.get("status") == "ocupado" and vaga.get("usuario") == nome_usuario
            for vaga in self.estado["vagas"]
        ):
            self.mensagem("Não é possível excluir um perfil com veículo estacionado.")
            return
        administradores = [
            conta for conta in self.estado["usuarios"].values()
            if conta.get("tipo") == "admin"
        ]
        if usuario.get("tipo") == "admin" and len(administradores) <= 1:
            self.mensagem("O último administrador não pode ser excluído.")
            return

        async def confirmar(e):
            alvo = self.estado["usuarios"].get(nome_usuario)
            ocupado = any(
                vaga.get("status") == "ocupado" and vaga.get("usuario") == nome_usuario
                for vaga in self.estado["vagas"]
            )
            admins = [
                conta for conta in self.estado["usuarios"].values()
                if conta.get("tipo") == "admin"
            ]
            if alvo is None or ocupado or (alvo.get("tipo") == "admin" and len(admins) <= 1):
                self.page.pop_dialog()
                self.mensagem("A exclusão não pode ser concluída: verifique as vagas ocupadas e os administradores.")
                return
            self.estado["usuarios"].pop(nome_usuario)
            await self.persistir()
            self.page.pop_dialog()
            if eh_proprio_perfil:
                self.usuario_logado = None
                self.mostrar_login()
            else:
                self.renderizar()
                self.mensagem("Perfil excluído.")

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Excluir perfil"),
                content=ft.Text(f"Tem certeza de que deseja excluir o perfil de {nome_usuario}? Esta ação não pode ser desfeita."),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=lambda e: self.page.pop_dialog()),
                    ft.Button(content=ft.Text("Excluir perfil"), on_click=confirmar),
                ],
            )
        )

    def abrir_edicao_perfil(self):
        usuario = self.estado["usuarios"][self.usuario_logado]
        email = ft.TextField(label="E-mail", value=usuario.get("email", ""), keyboard_type=ft.KeyboardType.EMAIL)
        telefone = ft.TextField(label="Telefone", value=usuario.get("telefone", ""), keyboard_type=ft.KeyboardType.PHONE)

        async def salvar(e):
            email_texto = (email.value or "").strip()
            telefone_texto = (telefone.value or "").strip()
            email.error = "Informe um e-mail válido" if email_texto and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_texto) else None
            self.page.update()
            if email.error:
                return
            usuario["email"] = email_texto
            usuario["telefone"] = telefone_texto
            await self.persistir()
            self.page.pop_dialog()
            self.renderizar()
            self.mensagem("Dados cadastrais atualizados.")

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Editar dados cadastrais"),
                content=ft.Column(tight=True, spacing=10, controls=[email, telefone]),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=lambda e: self.page.pop_dialog()),
                    ft.Button(content=ft.Text("Salvar"), on_click=salvar),
                ],
            )
        )

    def editar_veiculo(self, vaga_numero):
        vaga = next((v for v in self.estado["vagas"] if v["numero"] == vaga_numero), None)
        if not vaga or vaga.get("usuario") != self.usuario_logado:
            self.mensagem("Você só pode editar veículos vinculados à sua conta.")
            return
        modelo = ft.TextField(label="Modelo do veículo", value=vaga.get("modelo", ""))
        placa = ft.TextField(label="Placa", value=vaga.get("placa", ""))
        tipo_veiculo = ft.Dropdown(
            label="Tipo de veículo",
            value=vaga.get("tipo_veiculo") or "carro",
            options=[
                ft.DropdownOption(key="carro", text="Carro"),
                ft.DropdownOption(key="moto", text="Moto"),
            ],
        )

        async def salvar(e):
            modelo_texto = (modelo.value or "").strip()
            placa_texto = (placa.value or "").strip().upper()
            padrao = r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$|^[A-Z]{3}-?[0-9]{4}$"
            modelo.error = "Informe o modelo" if not modelo_texto else None
            duplicada = any(
                outra.get("status") == "ocupado"
                and outra["numero"] != vaga_numero
                and outra.get("placa") == placa_texto
                for outra in self.estado["vagas"]
            )
            placa_invalida = not re.match(padrao, placa_texto) or duplicada
            placa.error = "Informe a placa" if not placa_texto else ("Placa inválida" if placa_invalida else None)
            self.page.update()
            if modelo.error or placa.error:
                return
            vaga["modelo"] = modelo_texto
            vaga["placa"] = placa_texto
            vaga["tipo_veiculo"] = tipo_veiculo.value
            usuario = self.estado["usuarios"][self.usuario_logado]
            for veiculo in usuario.get("veiculos", []):
                if veiculo.get("vaga") == vaga_numero:
                    veiculo.update({
                        "modelo": modelo_texto,
                        "placa": placa_texto,
                        "tipo_veiculo": tipo_veiculo.value,
                    })
                    break
            await self.persistir()
            self.page.pop_dialog()
            self.renderizar()
            self.mensagem("Veículo atualizado.")

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Editar veículo · Vaga {vaga_numero}"),
                content=ft.Column(tight=True, spacing=10, controls=[tipo_veiculo, modelo, placa]),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=lambda e: self.page.pop_dialog()),
                    ft.Button(content=ft.Text("Salvar alterações"), on_click=salvar),
                ],
            )
        )

    def abrir_gerenciar_capacidade(self):
        if not self.eh_admin():
            self.mensagem("Somente um administrador pode gerenciar a capacidade.")
            return

        quantidades = {
            tipo: sum(
                vaga.get("tipo_vaga", "carro") == tipo
                for vaga in self.estado["vagas"]
            )
            for tipo in ("carro", "moto")
        }
        carros = ft.TextField(
            label="Quantidade de vagas para carros",
            value=str(quantidades["carro"]),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        motos = ft.TextField(
            label="Quantidade de vagas para motocicletas",
            value=str(quantidades["moto"]),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        aviso = ft.Text(
            "A redução só é permitida se as vagas removidas estiverem livres.",
            size=13,
        )

        async def salvar_capacidade(e):
            try:
                nova_quantidade = {
                    "carro": int((carros.value or "").strip()),
                    "moto": int((motos.value or "").strip()),
                }
            except ValueError:
                carros.error = "Informe uma quantidade inteira"
                motos.error = "Informe uma quantidade inteira"
                self.page.update()
                return

            carros.error = "Use zero ou um número positivo" if nova_quantidade["carro"] < 0 else None
            motos.error = "Use zero ou um número positivo" if nova_quantidade["moto"] < 0 else None
            if sum(nova_quantidade.values()) == 0:
                aviso.value = "O estacionamento precisa ter pelo menos uma vaga."
                self.page.update()
                return
            self.page.update()
            if carros.error or motos.error:
                return

            vagas_por_tipo = {
                tipo: sorted(
                    [v for v in self.estado["vagas"] if v.get("tipo_vaga", "carro") == tipo],
                    key=lambda vaga: vaga["numero"],
                )
                for tipo in ("carro", "moto")
            }
            for tipo, rotulo, campo in (
                ("carro", "carros", carros),
                ("moto", "motocicletas", motos),
            ):
                ocupadas = sum(v["status"] == "ocupado" for v in vagas_por_tipo[tipo])
                if nova_quantidade[tipo] < ocupadas:
                    campo.error = f"Há {ocupadas} {rotulo} estacionado(s); não é possível reduzir abaixo desse total."
            self.page.update()
            if carros.error or motos.error:
                return

            remapeamento = {}
            novas_vagas = []
            proximo_numero = 1
            for tipo in ("carro", "moto"):
                existentes = vagas_por_tipo[tipo]
                ocupadas = [v for v in existentes if v["status"] == "ocupado"]
                livres = [v for v in existentes if v["status"] == "livre"]
                mantidas = sorted(
                    ocupadas + livres[: nova_quantidade[tipo] - len(ocupadas)],
                    key=lambda vaga: vaga["numero"],
                )
                for vaga in mantidas:
                    antiga = vaga["numero"]
                    nova = dict(vaga)
                    nova["numero"] = proximo_numero
                    nova["tipo_vaga"] = tipo
                    remapeamento[antiga] = proximo_numero
                    novas_vagas.append(nova)
                    proximo_numero += 1
                while sum(v["tipo_vaga"] == tipo for v in novas_vagas) < nova_quantidade[tipo]:
                    novas_vagas.append({
                        "numero": proximo_numero,
                        "status": "livre",
                        "modelo": None,
                        "placa": None,
                        "usuario": None,
                        "entrada": None,
                        "tipo_veiculo": None,
                        "tipo_vaga": tipo,
                    })
                    proximo_numero += 1

            self.estado["vagas"] = novas_vagas
            for usuario in self.estado["usuarios"].values():
                for veiculo in usuario.get("veiculos", []):
                    numero_antigo = veiculo.get("vaga")
                    if numero_antigo in remapeamento:
                        veiculo["vaga"] = remapeamento[numero_antigo]

            await self.persistir()
            self.page.pop_dialog()
            self.renderizar()
            self.mensagem("Capacidade atualizada. A numeração das vagas foi reorganizada.")

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Gerenciar capacidade"),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text("Aumente ou diminua a capacidade por tipo de veículo."),
                        carros,
                        motos,
                        aviso,
                    ],
                ),
                actions=[
                    ft.TextButton(content=ft.Text("Cancelar"), on_click=lambda e: self.page.pop_dialog()),
                    ft.Button(content=ft.Text("Salvar capacidade"), on_click=salvar_capacidade),
                ],
            )
        )

    def view_perfil(self):
        usuario = self.estado["usuarios"][self.usuario_logado]
        veiculos = usuario.get("veiculos", [])
        tipo = "Gestor / Administrador" if self.eh_admin() else "Cliente"
        conteudo = [
            ft.Container(
                padding=18,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(self.usuario_logado[:1].upper(), size=28, color=AZUL, weight=ft.FontWeight.BOLD),
                        ft.Text(self.usuario_logado, size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(tipo, color=LARANJA if self.eh_admin() else AZUL),
                        ft.Text(f"E-mail: {usuario.get('email') or 'Não informado'}"),
                        ft.Text(f"Telefone: {usuario.get('telefone') or 'Não informado'}"),
                        ft.Text(f"{len(veiculos)} veículo(s) cadastrado(s)"),
                        ft.TextButton(content=ft.Text("Editar dados cadastrais"), on_click=lambda e: self.abrir_edicao_perfil()),
                        ft.Button(
                            content=ft.Text("Adicionar veículo"),
                            width=220,
                            on_click=lambda e: self.abrir_cadastro_veiculo(),
                        ),
                        *(
                            [
                                ft.Button(
                                    content=ft.Text("Aumentar vagas"),
                                    width=220,
                                    on_click=lambda e: self.abrir_gerenciar_capacidade(),
                                )
                            ]
                            if self.eh_admin()
                            else []
                        ),
                        ft.TextButton(
                            content=ft.Text("Excluir meu perfil"),
                            on_click=lambda e: self.solicitar_exclusao_perfil(self.usuario_logado),
                        ),
                    ],
                ),
            ),
        ]
        if self.eh_admin():
            perfis = [nome for nome in sorted(self.estado["usuarios"]) if nome != self.usuario_logado]
            conteudo.append(ft.Text("Gerenciar perfis", size=17, weight=ft.FontWeight.BOLD))
            if perfis:
                for nome in perfis:
                    tipo_perfil = "Administrador" if self.estado["usuarios"][nome].get("tipo") == "admin" else "Cliente"
                    conteudo.append(
                        ft.Card(
                            content=ft.Container(
                                padding=10,
                                content=ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Column(
                                            tight=True,
                                            controls=[ft.Text(nome, weight=ft.FontWeight.BOLD), ft.Text(tipo_perfil)],
                                        ),
                                        ft.TextButton(
                                            content=ft.Text("Excluir"),
                                            on_click=lambda e, alvo=nome: self.solicitar_exclusao_perfil(alvo),
                                        ),
                                    ],
                                ),
                            )
                        )
                    )
            else:
                conteudo.append(ft.Text("Não há outros perfis cadastrados."))

        conteudo.append(ft.Text("Veículos cadastrados", size=17, weight=ft.FontWeight.BOLD))
        if veiculos:
            for veiculo in veiculos:
                conteudo.append(
                    ft.Card(
                        content=ft.Container(
                            padding=12,
                            content=ft.Column(
                                spacing=6,
                                controls=[
                                    ft.Text(veiculo["modelo"], weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"{('Moto' if veiculo.get('tipo_veiculo') == 'moto' else 'Carro')} · "
                                        f"Placa: {veiculo['placa']} · Vaga {veiculo['vaga']}"
                                    ),
                                    ft.TextButton(
                                        content=ft.Text("Editar veículo"),
                                        on_click=lambda e, n=veiculo["vaga"]: self.editar_veiculo(n),
                                    ),
                                ],
                            ),
                        )
                    )
                )
        else:
            conteudo.append(ft.Text("Nenhum veículo cadastrado ainda."))
        return ft.Column(
            expand=True,
            controls=[ft.ListView(expand=True, spacing=6, padding=12, controls=conteudo)],
        )


async def main(page: ft.Page):
    page.title = "Click Vagas - Estacionamento"
    page.padding = 0
    # Tom claro estimado a partir do fundo da captura enviada.
    page.bgcolor = "#F5F9FA"
    page.theme_mode = ft.ThemeMode.LIGHT
    store = LocalStore()
    estado = await store.carregar(page)
    app = ClickVagasApp(page, store, estado)
    app.mostrar_login()


ft.run(main)
