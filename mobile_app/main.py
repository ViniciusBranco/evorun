import flet as ft
import httpx
import sqlite3
import datetime

API_URL = "http://127.0.0.1:8000"
APPBAR_BGCOLOR = ft.Colors.BLUE_800

# --- Configuração do Banco de Dados Local ---
def init_local_db():
    con = sqlite3.connect("evorun_local.db")
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            distance_km REAL NOT NULL,
            duration_minutes INTEGER NOT NULL,
            elevation_level INTEGER NOT NULL,
            workout_date TEXT NOT NULL,
            synced INTEGER DEFAULT 0
        )
    """)
    con.commit()
    con.close()

class AppState:
    """Uma classe para armazenar o estado da aplicação."""
    def __init__(self):
        self.token = None
        self.user_profile = {}

async def main(page: ft.Page):
    """Função principal que constrói e gerencia a interface do aplicativo."""
    page.title = "EvoRun"
    page.window_width = 400
    page.window_height = 850
    page.bgcolor = ft.Colors.BLUE_GREY_900
    
    app_state = AppState()

    # --- Lógica de API ---
    async def api_call(method, endpoint, data=None, json=None, headers=None):
        auth_headers = {}
        if app_state.token:
            auth_headers["Authorization"] = f"Bearer {app_state.token}"
        if headers:
            auth_headers.update(headers)
        
        async with httpx.AsyncClient() as client:
            if method == "POST":
                return await client.post(f"{API_URL}{endpoint}", data=data, json=json, headers=auth_headers)
            elif method == "GET":
                return await client.get(f"{API_URL}{endpoint}", headers=auth_headers)
            elif method == "PUT":
                return await client.put(f"{API_URL}{endpoint}", json=json, headers=auth_headers)

    # --- Controles da UI reutilizáveis ---
    email_field = ft.TextField(label="E-mail", width=300, keyboard_type=ft.KeyboardType.EMAIL, border_color=ft.Colors.BLUE_GREY_400)
    password_field = ft.TextField(label="Senha", width=300, password=True, can_reveal_password=True, border_color=ft.Colors.BLUE_GREY_400)
    remember_me_checkbox = ft.Checkbox(label="Lembrar-me")
    
    # --- Funções de Evento e Navegação ---
    async def logout(e=None):
        app_state.token = None
        app_state.user_profile = {}
        await page.client_storage.remove_async("remembered_email")
        await page.client_storage.remove_async("remembered_password")
        await show_view(login_container)

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

                user_response = await api_call("GET", "/api/v1/users/me/")
                if user_response.status_code == 200:
                    app_state.user_profile = user_response.json()
                    if not app_state.user_profile.get("full_name"):
                        await show_view(onboarding_container)
                    else:
                        await show_view(dashboard_container)
                else:
                    error_text_login.value = "Erro ao buscar perfil."
            else:
                error_text_login.value = "E-mail ou senha incorretos."
        except httpx.ConnectError:
            error_text_login.value = "Erro de conexão com o servidor."
        
        loading_indicator_login.visible = False
        login_button.disabled = False
        page.update()

    # --- Definição dos Containers de Tela ---
    login_button = ft.ElevatedButton("Entrar", width=300, on_click=login_clicked, bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE)
    error_text_login = ft.Text(value="", color=ft.Colors.RED_500)
    loading_indicator_login = ft.ProgressRing(visible=False)
    login_container = ft.Column([
        ft.Text("EvoRun", size=32, weight=ft.FontWeight.BOLD),
        email_field, password_field, remember_me_checkbox, login_button, loading_indicator_login, error_text_login
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, visible=True)

    onboarding_container = ft.Column(visible=False)
    dashboard_container = ft.Column(visible=False)
    profile_container = ft.Column(visible=False)
    workouts_container = ft.Column(visible=False)
    add_workout_container = ft.Column(visible=False)
    edit_profile_container = ft.Column(visible=False)

    # --- Funções que constroem o conteúdo das telas ---
    def build_onboarding_view():
        name_field = ft.TextField(label="Nome Completo", width=300)
        age_field = ft.TextField(label="Idade", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        weight_field = ft.TextField(label="Peso (kg)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        height_field = ft.TextField(label="Altura (cm)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        days_field = ft.TextField(label="Dias de treino/semana", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        error_text_onboarding = ft.Text(value="", color=ft.Colors.RED_500)

        async def save_profile(e):
            try:
                profile_data = {
                    "full_name": name_field.value, "age": int(age_field.value), "weight_kg": int(weight_field.value),
                    "height_cm": int(height_field.value), "training_days_per_week": int(days_field.value)
                }
                response = await api_call("PUT", "/api/v1/users/me/profile", json=profile_data)
                if response.status_code == 200:
                    app_state.user_profile = response.json()
                    await show_view(dashboard_container)
                else:
                    error_text_onboarding.value = f"Erro ao salvar: {response.text}"
                    page.update()
            except (ValueError, TypeError):
                error_text_onboarding.value = "Por favor, preencha todos os campos."
                page.update()
        
        onboarding_container.controls = [
            ft.Column([
                name_field, age_field, weight_field, height_field, days_field,
                ft.ElevatedButton("Salvar e Continuar", on_click=save_profile),
                error_text_onboarding
            ], scroll=ft.ScrollMode.AUTO, spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
        ]

    def build_dashboard_view():
        user_name = app_state.user_profile.get("full_name", "Usuário")
        dashboard_container.controls = [ft.Text(f"Bem-vindo, {user_name}!", size=24, weight=ft.FontWeight.BOLD)]

    def build_profile_view():
        async def go_to_edit_profile(e):
            await show_view(edit_profile_container)

        profile_container.controls = [
            ft.Text("Perfil do Usuário", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(f"Nome: {app_state.user_profile.get('full_name', '')}"),
            ft.Text(f"E-mail: {app_state.user_profile.get('email', '')}"),
            ft.Text(f"Idade: {app_state.user_profile.get('age', '')} anos"),
            ft.ElevatedButton("Editar Perfil", on_click=go_to_edit_profile)
        ]

    def build_edit_profile_view():
        name_edit_field = ft.TextField(label="Nome Completo", value=app_state.user_profile.get('full_name', ''), width=300)
        age_edit_field = ft.TextField(label="Idade", value=str(app_state.user_profile.get('age', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        weight_edit_field = ft.TextField(label="Peso (kg)", value=str(app_state.user_profile.get('weight_kg', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        height_edit_field = ft.TextField(label="Altura (cm)", value=str(app_state.user_profile.get('height_cm', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        days_edit_field = ft.TextField(label="Dias de treino/semana", value=str(app_state.user_profile.get('training_days_per_week', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        
        async def update_profile_clicked(e):
            updated_data = {
                "full_name": name_edit_field.value, "age": int(age_edit_field.value),
                "weight_kg": int(weight_edit_field.value), "height_cm": int(height_edit_field.value),
                "training_days_per_week": int(days_edit_field.value)
            }
            response = await api_call("PUT", "/api/v1/users/me/profile", json=updated_data)
            if response.status_code == 200:
                app_state.user_profile = response.json()
                await show_view(profile_container)
            else:
                print("Erro ao atualizar perfil")

        edit_profile_container.controls = [
            name_edit_field, age_edit_field, weight_edit_field, height_edit_field, days_edit_field,
            ft.ElevatedButton("Salvar Alterações", on_click=update_profile_clicked)
        ]

    async def build_workouts_view():
        workouts_list = ft.ListView(spacing=10, expand=True)
        
        async def go_to_add_workout(e):
            await show_view(add_workout_container)

        workouts_container.controls = [
            ft.FilledButton("Novo Treino", icon="add", on_click=go_to_add_workout),
            workouts_list
        ]
        
        response = await api_call("GET", "/api/v1/workouts/")
        if response.status_code == 200:
            workouts_data = response.json()
            workouts_list.controls.clear()
            for workout in workouts_data:
                workouts_list.controls.append(
                    ft.Row([
                        ft.Text(f"{datetime.datetime.fromisoformat(workout['workout_date']).strftime('%d/%m/%Y')} - {workout['distance_km']} km em {workout['duration_minutes']} min"),
                        ft.IconButton(ft.Icons.EDIT, on_click=lambda e, w_id=workout['id']: print(f"Editar treino ID: {w_id}"))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
        page.update()


    def build_add_workout_view():
        distance_field = ft.TextField(label="Distância (km)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        duration_field = ft.TextField(label="Duração (minutos)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        elevation_field = ft.TextField(label="Nível de Elevação", width=300, keyboard_type=ft.KeyboardType.NUMBER, value="0")
        
        async def save_workout_clicked(e):
            try:
                workout_data = {
                    "distance_km": float(distance_field.value),
                    "duration_minutes": int(duration_field.value),
                    "elevation_level": int(elevation_field.value)
                }
                
                con = sqlite3.connect("evorun_local.db")
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO workouts (distance_km, duration_minutes, elevation_level, workout_date) VALUES (?, ?, ?, ?)",
                    (workout_data["distance_km"], workout_data["duration_minutes"], workout_data["elevation_level"], datetime.datetime.now().isoformat())
                )
                con.commit()
                local_workout_id = cur.lastrowid
                con.close()
                print(f"Treino salvo localmente com ID: {local_workout_id}")

                response = await api_call("POST", "/api/v1/workouts/", json=workout_data)
                if response.status_code == 201:
                    print("Treino sincronizado com o backend!")
                    con = sqlite3.connect("evorun_local.db")
                    cur = con.cursor()
                    cur.execute("UPDATE workouts SET synced = 1 WHERE id = ?", (local_workout_id,))
                    con.commit()
                    con.close()
                else:
                    print(f"Erro ao sincronizar treino: {response.text}")
                await show_view(workouts_container)
            except (ValueError, TypeError):
                print("Erro: dados inválidos")
            except httpx.ConnectError:
                 print("Backend offline. Treino salvo localmente.")
                 await show_view(workouts_container)

        add_workout_container.controls = [
            distance_field, duration_field, elevation_field,
            ft.ElevatedButton("Salvar Treino", on_click=save_workout_clicked)
        ]

    # --- Gerenciador de Views ---
    async def show_view(view_to_show):
        if view_to_show == dashboard_container: build_dashboard_view()
        elif view_to_show == profile_container: build_profile_view()
        elif view_to_show == onboarding_container: build_onboarding_view()
        elif view_to_show == add_workout_container: build_add_workout_view()
        elif view_to_show == edit_profile_container: build_edit_profile_view()
        elif view_to_show == workouts_container: await build_workouts_view()

        navigation_bar.visible = view_to_show not in [login_container, onboarding_container]
        for view in [login_container, onboarding_container, dashboard_container, profile_container, add_workout_container, edit_profile_container, workouts_container]:
            view.visible = (view == view_to_show)
        page.update()

    # --- Barra de Navegação ---
    async def navigation_tapped(e):
        selected_index = e.control.selected_index
        if selected_index == 0: await show_view(dashboard_container)
        elif selected_index == 1: await show_view(workouts_container)
        elif selected_index == 2: await show_view(profile_container)
        elif selected_index == 3: await logout()

    navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Início"),
            ft.NavigationBarDestination(icon=ft.Icons.FITNESS_CENTER_OUTLINED, selected_icon=ft.Icons.FITNESS_CENTER, label="Treino"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON_OUTLINED, selected_icon=ft.Icons.PERSON, label="Perfil"),
            ft.NavigationBarDestination(icon=ft.Icons.LOGOUT, label="Sair"),
        ],
        on_change=navigation_tapped,
        visible=False
    )

    # --- Lógica de Inicialização ---
    init_local_db()
    page.add(
        ft.AppBar(title=ft.Text("EvoRun"), bgcolor=APPBAR_BGCOLOR),
        ft.Container(
            content=ft.Stack([login_container, onboarding_container, dashboard_container, profile_container, add_workout_container, edit_profile_container, workouts_container]),
            expand=True,
            alignment=ft.alignment.center
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
