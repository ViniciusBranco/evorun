import flet as ft
import httpx

API_URL = "http://127.0.0.1:8000"
APPBAR_BGCOLOR = ft.Colors.INDIGO_800

class AppState:
    """Uma classe para armazenar o estado da aplicação."""
    def __init__(self):
        self.token = None
        self.user_profile = {}

async def main(page: ft.Page):
    """Função principal que constrói e gerencia a interface do aplicativo."""
    page.title = "EvoRun Mobile"
    page.window_width = 400
    page.window_height = 850
    page.bgcolor = ft.Colors.BLUE_GREY_900
    page.theme_mode = ft.ThemeMode.DARK
    
    app_state = AppState()

    # --- Lógica de API ---
    async def api_call(method, endpoint, data=None, headers=None):
        async with httpx.AsyncClient() as client:
            if method == "POST":
                return await client.post(f"{API_URL}{endpoint}", data=data, headers=headers)
            elif method == "GET":
                return await client.get(f"{API_URL}{endpoint}", headers=headers)
            elif method == "PUT":
                return await client.put(f"{API_URL}{endpoint}", json=data, headers=headers)

    # --- Controles da UI (reutilizáveis em múltiplos containers) ---
    email_field = ft.TextField(label="E-mail", width=300, keyboard_type=ft.KeyboardType.EMAIL, border_color=ft.Colors.BLUE_GREY_400)
    password_field = ft.TextField(label="Senha", width=300, password=True, can_reveal_password=True, border_color=ft.Colors.BLUE_GREY_400)
    remember_me_checkbox = ft.Checkbox(label="Lembrar-me")
    error_text_login = ft.Text(value="", color=ft.Colors.RED_500)
    loading_indicator_login = ft.ProgressRing(visible=False)
    versao = ft.Text("Versão 0.1.0", size=12, color=ft.Colors.BLUE_GREY_300)

    name_field = ft.TextField(label="Nome Completo", width=300)
    age_field = ft.TextField(label="Idade", width=300, keyboard_type=ft.KeyboardType.NUMBER)
    weight_field = ft.TextField(label="Peso (kg)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
    height_field = ft.TextField(label="Altura (cm)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
    days_field = ft.TextField(label="Dias de treino/semana", width=300, keyboard_type=ft.KeyboardType.NUMBER)
    error_text_onboarding = ft.Text(value="", color=ft.Colors.RED_500)

    # --- Funções de Evento ---
    async def login_clicked(e):
        loading_indicator_login.visible = True
        login_button.disabled = True
        error_text_login.value = ""
        page.update()
        
        try:
            response = await api_call("POST", "/api/v1/login/token", data={'username': email_field.value, 'password': password_field.value})
            if response.status_code == 200:
                app_state.token = response.json().get("access_token")
                
                if remember_me_checkbox.value:
                    await page.client_storage.set_async("remembered_email", email_field.value)
                    await page.client_storage.set_async("remembered_password", password_field.value)
                else:
                    await page.client_storage.remove_async("remembered_email")
                    await page.client_storage.remove_async("remembered_password")

                headers = {"Authorization": f"Bearer {app_state.token}"}
                user_response = await api_call("GET", "/api/v1/users/me/", headers=headers)
                if user_response.status_code == 200:
                    app_state.user_profile = user_response.json()
                    if not app_state.user_profile.get("full_name"):
                        show_view(onboarding_container)
                    else:
                        show_view(dashboard_container)
                else:
                    error_text_login.value = "Erro ao buscar perfil."
            else:
                error_text_login.value = "E-mail ou senha incorretos."
        except httpx.ConnectError:
            error_text_login.value = "Erro de conexão com o servidor."
        
        loading_indicator_login.visible = False
        login_button.disabled = False
        page.update()

    async def save_profile(e):
        try:
            profile_data = {
                "full_name": name_field.value, "age": int(age_field.value), "weight_kg": int(weight_field.value),
                "height_cm": int(height_field.value), "training_days_per_week": int(days_field.value)
            }
            headers = {"Authorization": f"Bearer {app_state.token}"}
            response = await api_call("PUT", "/api/v1/users/me/profile", data=profile_data, headers=headers)
            if response.status_code == 200:
                app_state.user_profile = response.json()
                show_view(dashboard_container)
            else:
                error_text_onboarding.value = f"Erro ao salvar: {response.text}"
                page.update()
        except (ValueError, TypeError):
            error_text_onboarding.value = "Por favor, preencha todos os campos corretamente."
            page.update()

    async def logout(e=None):
        app_state.token = None
        app_state.user_profile = {}
        await page.client_storage.remove_async("remembered_email")
        await page.client_storage.remove_async("remembered_password")
        show_view(login_container)

    # --- Definição dos Containers de Tela ---
    login_button = ft.ElevatedButton("Entrar", width=300, on_click=login_clicked, bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE)
    login_container = ft.Column([
        ft.Text("EvoRun", size=32, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
        email_field, password_field, remember_me_checkbox, login_button, loading_indicator_login, error_text_login, versao,
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, visible=True)

    onboarding_container = ft.Column([
        ft.AppBar(title=ft.Text("Complete seu Perfil"), bgcolor=APPBAR_BGCOLOR, leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=logout)),
        ft.Column([
            name_field, age_field, weight_field, height_field, days_field,
            ft.ElevatedButton("Salvar e Continuar", on_click=save_profile),
            error_text_onboarding
        ], scroll=ft.ScrollMode.AUTO, spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
    ], visible=False)

    dashboard_container = ft.Column(visible=False)
    profile_container = ft.Column(visible=False)
    plans_container = ft.Column(visible=False)

    def dashboard_view():
        user_name = app_state.user_profile.get("full_name", "Usuário")
        dashboard_container.controls = [
            ft.Text(f"Bem-vindo, {user_name}!", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Aqui estarão os resumos e último treino realizado.")
        ]

    def profile_view():
        profile_container.controls = [
            ft.Text("Perfil do Usuário", size=24, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.LEFT),
            ft.Text(f"Nome: {app_state.user_profile.get('full_name', '')}"),
            ft.Text(f"E-mail: {app_state.user_profile.get('email', '')}"),
            ft.Text(f"Idade: {app_state.user_profile.get('age', '')}"),
            ft.Text(f"Peso: {app_state.user_profile.get('weight_kg', '')} kg"),
            ft.Text(f"Altura: {app_state.user_profile.get('height_cm', '')} cm"),
            ft.Text(f"Dias de treino/semana: {app_state.user_profile.get('training_days_per_week', '')}")
        ]
    
    def plans_view():
        plans_container.controls = [
            ft.Text("Planos de Treino", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Aqui estarão os planos de treino personalizados.")
        ]

    # --- Gerenciador de Views ---
    def show_view(view_to_show):
        if view_to_show == dashboard_container:
            dashboard_view()
        elif view_to_show == profile_container:
            profile_view()
        elif view_to_show == plans_container:
            plans_view()
        navigation_bar.visible = (view_to_show != login_container and view_to_show != onboarding_container)
        for view in [login_container, onboarding_container, dashboard_container, profile_container, plans_container]:
            view.visible = (view == view_to_show)
        page.update()

    # --- Barra de Navegação ---
    async def navigation_tapped(e):
        selected_index = e.control.selected_index

        if selected_index == 0:
            show_view(dashboard_container)
        elif selected_index == 1:
            show_view(profile_container)
        elif selected_index == 2:
            show_view(plans_container)
        elif selected_index == 3:
            await logout()

    navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Início"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON_OUTLINED, selected_icon=ft.Icons.PERSON, label="Perfil"),
            ft.NavigationBarDestination(icon=ft.Icons.INSERT_CHART_OUTLINED, selected_icon=ft.Icons.INSERT_CHART, label="Planos"),
            ft.NavigationBarDestination(icon=ft.Icons.LOGOUT, label="Sair"),
        ],
        on_change=navigation_tapped,
        visible=False
    )

    # --- Lógica de Inicialização ---
    page.add(
        # ft.AppBar(title=ft.Text("Evolving Runner"), bgcolor=APPBAR_BGCOLOR),
        ft.Container(
            content=ft.Stack([login_container, onboarding_container, dashboard_container, profile_container, plans_container]),
            expand=True,
        ),
        navigation_bar
    )

    remembered_email = await page.client_storage.get_async("remembered_email")
    remembered_password = await page.client_storage.get_async("remembered_password")
    if remembered_email and remembered_password:
        email_field.value = remembered_email
        password_field.value = remembered_password
        remember_me_checkbox.value = True
        page.update()

ft.app(target=main, view=ft.AppView.FLET_APP)
