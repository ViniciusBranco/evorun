import flet as ft
import httpx
import sqlite3
import datetime
import calendar
import json

# # --- IMPORTS DO GRÁFICO (TEMPORARIAMENTE DESATIVADOS PARA O BUILD) ---
# import matplotlib
# import matplotlib.pyplot as plt
# from flet.matplotlib_chart import MatplotlibChart
# # Configura o backend do Matplotlib para renderizar em SVG, ideal para o Flet.
# matplotlib.use("svg")

# --- Constantes Globais ---
# ATENÇÃO: Use 127.0.0.1 para testes locais no PC. Use o IP da rede para builds no telemóvel.
API_URL = "http://127.0.0.1:8000" # Exemplo para build: "http://192.168.1.5:8000"
APPBAR_BGCOLOR = ft.Colors.BLUE_800

# Dicionário central para a aparência dos treinos na UI.
WORKOUT_VISUALS = {
    "running": {"icon": ft.Icons.DIRECTIONS_RUN, "color": ft.Colors.GREEN, "name": "Corrida"},
    "cycling": {"icon": ft.Icons.DIRECTIONS_BIKE, "color": ft.Colors.BROWN, "name": "Ciclismo"},
    "swimming": {"icon": ft.Icons.POOL, "color": ft.Colors.BLUE, "name": "Natação"},
    "weightlifting": {"icon": ft.Icons.FITNESS_CENTER, "color": ft.Colors.PURPLE, "name": "Musculação"},
    "stairs": {"icon": ft.Icons.STAIRS, "color": ft.Colors.AMBER, "name": "Escada"}
}

# --- Lógica do Banco de Dados Local ---

def init_local_db():
    """Inicializa o banco de dados SQLite local com as tabelas necessárias."""
    with sqlite3.connect("evorun_local.db") as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, api_id INTEGER UNIQUE, user_email TEXT NOT NULL,
                workout_type TEXT NOT NULL, workout_date TEXT NOT NULL, duration_minutes INTEGER,
                distance_km REAL, details TEXT, synced INTEGER DEFAULT 0, to_be_deleted INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                email TEXT PRIMARY KEY, full_name TEXT, age INTEGER, weight_kg INTEGER,
                height_cm INTEGER, training_days_per_week INTEGER, synced INTEGER DEFAULT 1
            )
        """)
        con.commit()

def save_profile_locally(profile_data: dict, synced: int):
    """Salva ou atualiza os dados de um perfil de usuário no banco local."""
    with sqlite3.connect("evorun_local.db") as con:
        cur = con.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO user_profile (email, full_name, age, weight_kg, height_cm, training_days_per_week, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            profile_data.get('email'), profile_data.get('full_name'), profile_data.get('age'),
            profile_data.get('weight_kg'), profile_data.get('height_cm'),
            profile_data.get('training_days_per_week'), synced
        ))
        con.commit()

def load_profile_locally(email: str):
    """Carrega os dados de um perfil de usuário específico do banco local."""
    if not email: return None
    with sqlite3.connect("evorun_local.db") as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM user_profile WHERE email = ?", (email,))
        row = cur.fetchone()
        return dict(row) if row else None

def sync_workouts_from_api(user_email: str, workouts_from_api: list):
    """Sincroniza os treinos da API com o banco de dados local."""
    with sqlite3.connect("evorun_local.db") as con:
        cur = con.cursor()
        for workout in workouts_from_api:
            cur.execute("""
                INSERT INTO workouts (api_id, user_email, workout_type, workout_date, duration_minutes, distance_km, details, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(api_id) DO UPDATE SET
                    workout_type=excluded.workout_type, workout_date=excluded.workout_date,
                    duration_minutes=excluded.duration_minutes, distance_km=excluded.distance_km,
                    details=excluded.details, synced=1
            """, (
                workout['id'], user_email, workout['workout_type'], workout['workout_date'],
                workout.get('duration_minutes'), workout.get('distance_km'),
                json.dumps(workout.get('details')),
            ))
        con.commit()
    print(f"{len(workouts_from_api)} treinos sincronizados do backend para o local.")

# --- Estado da Aplicação ---

class AppState:
    """Uma classe simples para armazenar o estado global da aplicação."""
    def __init__(self):
        self.token: str | None = None
        self.user_profile: dict = {}
        self.editing_workout_id: int | None = None
        self.current_calendar_date: datetime.date = datetime.date.today()

# --- Função Principal da Aplicação ---

async def main(page: ft.Page):
    """Função principal que constrói e gerencia a interface do aplicativo Flet."""
    page.title = "EvoRun"
    page.window.width = 400
    page.window.height = 850
    page.bgcolor = ft.Colors.BLUE_GREY_900

    app_state = AppState()

    # --- Lógica de Sincronização ---
    async def sync_local_changes_to_backend():
        """Verifica alterações locais (offline) e as envia para o backend."""
        print("Verificando alterações locais para sincronizar...")
        if not app_state.token or not app_state.user_profile.get('email'):
            print("Sincronização abortada: sem token ou perfil de usuário.")
            return

        with sqlite3.connect("evorun_local.db") as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM user_profile WHERE email = ? AND synced = 0", (app_state.user_profile['email'],))
            unsynced_profile = cur.fetchone()
            if unsynced_profile:
                profile_data = dict(unsynced_profile)
                print("Enviando perfil não sincronizado...")
                payload = {k: v for k, v in profile_data.items() if k not in ['email', 'synced']}
                response = await api_call("PUT", "/api/v1/users/me/profile", json=payload)
                if response and response.status_code == 200:
                    save_profile_locally(response.json(), synced=1)
                    print("Perfil sincronizado com sucesso.")

            cur.execute("SELECT * FROM workouts WHERE user_email = ? AND synced = 0 AND to_be_deleted = 0", (app_state.user_profile['email'],))
            unsynced_workouts = cur.fetchall()
            if unsynced_workouts:
                print(f"Enviando {len(unsynced_workouts)} treinos não sincronizados...")
                for workout_row in unsynced_workouts:
                    workout = dict(workout_row)
                    workout_data = {
                        "workout_type": workout['workout_type'], "workout_date": workout['workout_date'],
                        "duration_minutes": workout.get('duration_minutes'), "distance_km": workout.get('distance_km'),
                        "details": json.loads(workout['details']) if workout.get('details') else {}
                    }
                    endpoint = f"/api/v1/workouts/{workout['api_id']}" if workout.get('api_id') else "/api/v1/workouts/"
                    method = "PUT" if workout.get('api_id') else "POST"
                    response = await api_call(method, endpoint, json=workout_data)
                    if response and response.status_code in [200, 201]:
                        api_id = response.json().get("id")
                        cur.execute("UPDATE workouts SET synced = 1, api_id = ? WHERE id = ?", (api_id, workout['id']))
                        con.commit()
                        print(f"Treino local ID {workout['id']} sincronizado.")
                    elif response is None:
                        print("Não foi possível sincronizar treinos. Backend offline.")
                        break

            cur.execute("SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 1", (app_state.user_profile['email'],))
            workouts_to_delete = cur.fetchall()
            if workouts_to_delete:
                print(f"Enviando {len(workouts_to_delete)} exclusões de treinos...")
                for workout_row in workouts_to_delete:
                    workout = dict(workout_row)
                    if workout.get('api_id'):
                        response = await api_call("DELETE", f"/api/v1/workouts/{workout['api_id']}")
                        if response and response.status_code in [200, 204, 404]:
                            cur.execute("DELETE FROM workouts WHERE id = ?", (workout['id'],))
                            con.commit()
                            print(f"Treino ID {workout['id']} excluído permanentemente.")
                        elif response is None:
                            print("Não foi possível sincronizar exclusões. Backend offline.")
                            break
                    else:
                        cur.execute("DELETE FROM workouts WHERE id = ?", (workout['id'],))
                        con.commit()
                        print(f"Treino local ID {workout['id']} (nunca sincronizado) excluído permanentemente.")

    # --- Funções Auxiliares de UI e API ---
    async def api_call(method, endpoint, data=None, json=None, headers=None):
        """Função central para fazer chamadas à API do backend."""
        auth_headers = {}
        if app_state.token:
            auth_headers["Authorization"] = f"Bearer {app_state.token}"
        if headers:
            auth_headers.update(headers)
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if method == "POST": return await client.post(f"{API_URL}{endpoint}", data=data, json=json, headers=auth_headers)
                elif method == "GET": return await client.get(f"{API_URL}{endpoint}", headers=auth_headers)
                elif method == "PUT": return await client.put(f"{API_URL}{endpoint}", json=json, headers=auth_headers)
                elif method == "DELETE": return await client.delete(f"{API_URL}{endpoint}", headers=auth_headers)
        except httpx.RequestError as e:
            print(f"Erro de conexão com a API: {e}")
            return None

    async def delete_workout_confirmed(e):
        """Marca um treino para exclusão no banco local e atualiza a UI."""
        local_id_to_delete = delete_bs.data.get("local_id")
        with sqlite3.connect("evorun_local.db") as con:
            cur = con.cursor()
            cur.execute("UPDATE workouts SET to_be_deleted = 1, synced = 0 WHERE id = ?", (local_id_to_delete,))
            con.commit()
        print(f"Treino local ID {local_id_to_delete} marcado para exclusão.")
        close_bs()
        await show_view(workouts_container)

    def close_bs(e=None):
        """Fecha o BottomSheet (diálogo de confirmação)."""
        delete_bs.open = False
        page.update()

    # --- Definição dos Controles da UI ---
    delete_bs = ft.BottomSheet(ft.Container(), on_dismiss=close_bs)
    page.overlay.append(delete_bs)

    # --- Lógica de Eventos Principais ---

    async def login_clicked(e):
        """Lida com a lógica de login, tanto online quanto offline."""
        loading_indicator_login.visible = True
        login_button.disabled = True
        error_text_login.value = ""
        page.update()
        
        response = await api_call("POST", "/api/v1/login/token", data={'username': email_field.value, 'password': password_field.value})

        if response is None:
            print("Conexão falhou. Tentando login offline com base no perfil local.")
            local_profile = load_profile_locally(email_field.value)
            if local_profile:
                print("Perfil local encontrado. Concedendo acesso offline.")
                app_state.user_profile = local_profile
                app_state.token = "offline-token" # Token simbólico para estado offline
                await show_view(dashboard_container)
            else:
                print("Nenhum perfil local encontrado para login offline.")
                error_text_login.value = "Offline. Apenas contas já usadas podem entrar."

        elif response.status_code == 200:
            app_state.token = response.json().get("access_token")
            user_response = await api_call("GET", "/api/v1/users/me/")
            
            if user_response and user_response.status_code == 200:
                app_state.user_profile = user_response.json()
                await sync_local_changes_to_backend()
                final_user_response = await api_call("GET", "/api/v1/users/me/")
                if final_user_response:
                    app_state.user_profile = final_user_response.json()
                
                save_profile_locally(app_state.user_profile, synced=1)
                workouts_response = await api_call("GET", "/api/v1/workouts/")
                if workouts_response and workouts_response.status_code == 200:
                    sync_workouts_from_api(app_state.user_profile['email'], workouts_response.json())
                
                if remember_me_checkbox.value:
                    await page.client_storage.set_async("remembered_email", email_field.value)
                    await page.client_storage.set_async("remembered_password", password_field.value)
                
                if not app_state.user_profile.get("full_name"):
                    await show_view(onboarding_container)
                else:
                    await show_view(dashboard_container)
            else:
                error_text_login.value = "Erro ao buscar perfil."
        else:
            error_text_login.value = "E-mail ou senha incorretos."

        loading_indicator_login.visible = False
        login_button.disabled = False
        page.update()

    email_field = ft.TextField(label="E-mail", width=300, keyboard_type=ft.KeyboardType.EMAIL, border_color=ft.Colors.BLUE_GREY_400)
    password_field = ft.TextField(label="Senha", width=300, password=True, can_reveal_password=True, border_color=ft.Colors.BLUE_GREY_400)
    remember_me_checkbox = ft.Checkbox(label="Lembrar-me")
    login_button = ft.ElevatedButton("Entrar", width=300, on_click=login_clicked, bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE)
    error_text_login = ft.Text(value="", color=ft.Colors.RED_500)
    loading_indicator_login = ft.ProgressRing(visible=False)

    async def logout(e=None):
        """Limpa o estado da aplicação e retorna para a tela de login."""
        app_state.token = None
        app_state.user_profile = {}
        await show_view(login_container)

    # --- Containers de Tela (Views) ---
    login_container = ft.Column([ft.Text("EvoRun", size=32, weight=ft.FontWeight.BOLD), email_field, password_field, remember_me_checkbox, login_button, loading_indicator_login, error_text_login], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, visible=True, expand=True, scroll=ft.ScrollMode.AUTO)
    onboarding_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll=ft.ScrollMode.AUTO)
    dashboard_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True) # Scroll removido para o gráfico expandir
    profile_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll=ft.ScrollMode.AUTO)
    edit_profile_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll=ft.ScrollMode.AUTO)
    workouts_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)
    add_workout_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll=ft.ScrollMode.AUTO)
    edit_workout_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll=ft.ScrollMode.AUTO)

    all_views = [login_container, onboarding_container, dashboard_container,
                 profile_container, add_workout_container, edit_profile_container,
                 workouts_container, edit_workout_container]
    
    # --- Funções de Construção de Views ---
    async def build_dashboard_view():
        """
        Constrói o conteúdo da tela de dashboard.
        """
        user_name = "Usuário"
        full_name = app_state.user_profile.get("full_name")
        if full_name:
            user_name = full_name.split(" ")[0]

        dashboard_container.controls = [
            ft.Text(f"Olá, {user_name}!", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Funcionalidade de gráficos temporariamente desativada para o build.", italic=True)
        ]
        page.update()

    def build_profile_view():
        """Constrói o conteúdo da tela de visualização de perfil."""
        async def go_to_edit_profile(e):
            await show_view(edit_profile_container)
        
        profile_card = ft.Card(
            content=ft.Container(
                padding=20,
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.PERSON_ROUNDED, size=30), ft.Text("Perfil do Usuário", size=24, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    ft.Text(f"Nome: {app_state.user_profile.get('full_name', 'Não informado')}"),
                    ft.Text(f"E-mail: {app_state.user_profile.get('email', '')}"),
                    ft.Text(f"Idade: {app_state.user_profile.get('age', 'Não informada')} anos"),
                    ft.Text(f"Peso: {app_state.user_profile.get('weight_kg', 'Não informado')} kg"),
                    ft.Text(f"Altura: {app_state.user_profile.get('height_cm', 'Não informada')} cm"),
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    ft.ElevatedButton("Editar Perfil", icon=ft.Icons.EDIT, on_click=go_to_edit_profile, width=250),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            )
        )
        profile_container.controls = [profile_card]

    def build_onboarding_view():
        """Constrói o conteúdo da tela de onboarding."""
        name_field = ft.TextField(label="Nome Completo", width=300)
        age_field = ft.TextField(label="Idade", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        weight_field = ft.TextField(label="Peso (kg)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        height_field = ft.TextField(label="Altura (cm)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        days_field = ft.TextField(label="Dias de treino/semana", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        error_text_onboarding = ft.Text(value="", color=ft.Colors.RED_500)
        async def save_profile(e):
            if not all([name_field.value, age_field.value, weight_field.value, height_field.value, days_field.value]):
                error_text_onboarding.value = "Todos os campos são obrigatórios."
                page.update()
                return
            try:
                profile_data = {
                    "full_name": name_field.value, "age": int(age_field.value),
                    "weight_kg": int(weight_field.value), "height_cm": int(height_field.value),
                    "training_days_per_week": int(days_field.value)
                }
            except ValueError:
                error_text_onboarding.value = "Por favor, insira apenas números nos campos numéricos."
                page.update()
                return
            
            app_state.user_profile.update(profile_data)
            save_profile_locally(app_state.user_profile, synced=0)
            
            response = await api_call("PUT", "/api/v1/users/me/profile", json=profile_data)
            if response and response.status_code == 200:
                app_state.user_profile = response.json()
                save_profile_locally(app_state.user_profile, synced=1)
            elif response is not None:
                error_text_onboarding.value = f"Ocorreu um erro no servidor ({response.status_code})."
                page.update()
                return # Impede a navegação se houver erro de API
            
            # Prossegue para o dashboard em caso de sucesso ou offline
            print("Perfil salvo. Prosseguindo para o dashboard.")
            await show_view(dashboard_container)

        onboarding_container.controls = [ft.Column([
            ft.Text("Complete seu Perfil", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Precisamos de mais algumas informações para começar."),
            name_field, age_field, weight_field, height_field, days_field,
            ft.ElevatedButton("Salvar e Continuar", on_click=save_profile),
            error_text_onboarding
        ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER)]

    def build_edit_profile_view():
        """Constrói o conteúdo da tela de edição de perfil."""
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
            app_state.user_profile.update(updated_data)
            save_profile_locally(app_state.user_profile, synced=0)
            
            response = await api_call("PUT", "/api/v1/users/me/profile", json=updated_data)
            if response and response.status_code == 200:
                app_state.user_profile = response.json()
                save_profile_locally(app_state.user_profile, synced=1)
                print("Perfil sincronizado com sucesso.")
            elif response is None:
                print("Backend offline. Perfil atualizado localmente.")
            
            await show_view(profile_container)

        async def cancel_edit_profile(e):
            await show_view(profile_container)
            
        edit_profile_container.controls = [
            ft.Text("Editar Perfil", size=24, weight=ft.FontWeight.BOLD),
            name_edit_field, age_edit_field, weight_edit_field, height_edit_field, days_edit_field,
            ft.Row([
                ft.ElevatedButton("Cancelar", on_click=cancel_edit_profile, bgcolor=ft.Colors.GREY),
                ft.ElevatedButton("Salvar Alterações", on_click=update_profile_clicked),
            ], alignment=ft.MainAxisAlignment.CENTER)
        ]

    # --- Funções de Construção de Views de Treino ---
    def _build_workout_form(workout_data: dict | None = None):
        """Constrói um formulário de treino dinâmico e reutilizável."""
        is_editing = workout_data is not None
        
        if is_editing and workout_data.get('workout_date'):
            initial_date = datetime.datetime.fromisoformat(workout_data['workout_date'])
        else:
            initial_date = datetime.datetime.combine(app_state.current_calendar_date, datetime.datetime.now().time())

        workout_type_dropdown = ft.Dropdown(
            label="Tipo de Treino",
            options=[ft.dropdown.Option(key=k, text=v['name']) for k, v in WORKOUT_VISUALS.items()],
            value=workout_data.get('workout_type') if is_editing else "running"
        )
        
        date_picker = ft.DatePicker(
            first_date=datetime.datetime(2020, 1, 1),
            last_date=datetime.datetime.now() + datetime.timedelta(days=365),
            current_date=initial_date,
        )
        page.overlay.append(date_picker)
        def open_date_picker(e):
            page.open(date_picker)
        date_button = ft.ElevatedButton("Escolher Data", icon=ft.Icons.CALENDAR_MONTH, on_click=open_date_picker)
        date_text = ft.Text(value=initial_date.strftime("%d/%m/%Y"))
        def update_date_text(e):
            date_text.value = date_picker.value.strftime("%d/%m/%Y")
            page.update()
        date_picker.on_change = update_date_text
        duration_field = ft.TextField(label="Duração (min)", keyboard_type=ft.KeyboardType.NUMBER, value=str(workout_data.get('duration_minutes', '')) if is_editing else "")
        distance_field = ft.TextField(label="Distância (km)", keyboard_type=ft.KeyboardType.NUMBER, value=str(workout_data.get('distance_km', '')) if is_editing else "")
        details = json.loads(workout_data.get('details', '{}')) if is_editing else {}
        elevation_field = ft.TextField(label="Ganho de Elevação (m)", keyboard_type=ft.KeyboardType.NUMBER, value=str(details.get('elevation_level', '')))
        pool_size_field = ft.TextField(label="Tamanho da Piscina (m)", keyboard_type=ft.KeyboardType.NUMBER, value=str(details.get('pool_size_meters', '')))
        # Campos de musculação
        exercise_field = ft.TextField(label="Exercício", value=details.get('exercise', ''))
        sets_field = ft.TextField(label="Séries", keyboard_type=ft.KeyboardType.NUMBER, value=str(details.get('sets', '')))
        reps_field = ft.TextField(label="Repetições", keyboard_type=ft.KeyboardType.NUMBER, value=str(details.get('reps', '')))
        weight_field = ft.TextField(label="Carga Total (kg)", keyboard_type=ft.KeyboardType.NUMBER, value=str(details.get('weight_kg', '')))
        # Campo de escada
        steps_field = ft.TextField(label="Degraus (opcional)", keyboard_type=ft.KeyboardType.NUMBER, value=str(details.get('steps', '')))
        
        details_container = ft.Column()
        def update_form_fields(e=None):
            selected_type = workout_type_dropdown.value
            duration_field.visible = selected_type not in ["weightlifting"]
            distance_field.visible = selected_type in ["running", "cycling", "swimming"]
            elevation_field.visible = selected_type in ["running", "cycling"]
            pool_size_field.visible = selected_type == "swimming"
            exercise_field.visible = False # Manter invisível
            sets_field.visible = False # Manter invisível
            reps_field.visible = False # Manter invisível
            weight_field.visible = selected_type == "weightlifting"
            steps_field.visible = selected_type == "stairs" # Apenas para escada
            
            # Adicionar a nova condição para a duração ficar visível em "Escada"
            if selected_type == "stairs":
                duration_field.visible = True

            details_container.controls = [
                field for field in [elevation_field, pool_size_field, exercise_field, sets_field, reps_field, weight_field, steps_field]
                if field.visible
            ]
            page.update()
        workout_type_dropdown.on_change = update_form_fields
        
        async def save_workout_clicked(e):
            details_payload = {}
            selected_type = workout_type_dropdown.value
            if selected_type in ["running", "cycling"]: 
                details_payload['elevation_level'] = int(elevation_field.value or 0)
            if selected_type == "swimming": 
                details_payload['pool_size_meters'] = int(pool_size_field.value or 50)
            if selected_type == "weightlifting":
                details_payload = {
                    'exercise': "Treino de Força", 'sets': 1, 'reps': 1,
                    'weight_kg': float(weight_field.value or 0.0)
                }
            if selected_type == "stairs":
                # Tratar valor vazio para degraus opcionais
                steps_value = steps_field.value
                details_payload = {
                    'steps': int(steps_value) if steps_value else None
                }

            api_payload = {
                'workout_type': selected_type,
                'workout_date': (date_picker.value or initial_date).isoformat(),
                'duration_minutes': int(duration_field.value or 0) if duration_field.visible else None,
                'distance_km': float(distance_field.value or 0.0) if distance_field.visible else None,
                'details': details_payload
            }
            local_payload = api_payload.copy()
            local_payload['user_email'] = app_state.user_profile['email']
            local_payload['details'] = json.dumps(details_payload)

            local_id, api_id_before_save = None, None
            with sqlite3.connect("evorun_local.db") as con:
                cur = con.cursor()
                if is_editing:
                    local_id = app_state.editing_workout_id
                    cur.execute("SELECT api_id FROM workouts WHERE id = ?", (local_id,))
                    result = cur.fetchone()
                    api_id_before_save = result[0] if result else None
                    cur.execute("""
                        UPDATE workouts SET workout_type=?, workout_date=?, duration_minutes=?, distance_km=?, details=?, synced=0
                        WHERE id = ?
                    """, (
                        local_payload['workout_type'], local_payload['workout_date'], local_payload['duration_minutes'],
                        local_payload['distance_km'], local_payload['details'], local_id
                    ))
                else:
                    cur.execute("""
                        INSERT INTO workouts (user_email, workout_type, workout_date, duration_minutes, distance_km, details, synced)
                        VALUES (?, ?, ?, ?, ?, ?, 0)
                    """, (
                        local_payload['user_email'], local_payload['workout_type'], local_payload['workout_date'],
                        local_payload['duration_minutes'], local_payload['distance_km'], local_payload['details']
                    ))
                    local_id = cur.lastrowid
                con.commit()

            endpoint = f"/api/v1/workouts/{api_id_before_save}" if is_editing and api_id_before_save else "/api/v1/workouts/"
            method = "PUT" if is_editing and api_id_before_save else "POST"
            response = await api_call(method, endpoint, json=api_payload)

            if response and response.status_code in [200, 201]:
                print("Sincronização do treino bem-sucedida.")
                api_id = response.json().get("id")
                with sqlite3.connect("evorun_local.db") as con:
                    cur = con.cursor()
                    cur.execute("UPDATE workouts SET synced = 1, api_id = ? WHERE id = ?", (api_id, local_id))
                    con.commit()
            elif response is None:
                print("Backend offline. Treino salvo localmente para sincronização futura.")
            else:
                print(f"Falha ao sincronizar treino com o backend. Status: {response.status_code}, Resposta: {response.text}")
            
            await show_view(workouts_container)

        update_form_fields()
        async def cancel_workout_form(e):
            await show_view(workouts_container)
        return ft.Column([
            ft.Text("Editar Treino" if is_editing else "Adicionar Treino", size=24, weight=ft.FontWeight.BOLD),
            workout_type_dropdown,
            ft.Row([date_button, date_text], alignment=ft.MainAxisAlignment.CENTER),
            duration_field, distance_field, ft.Divider(),
            ft.Text("Detalhes Específicos", italic=True), details_container,
            ft.Row([
                ft.ElevatedButton("Cancelar", on_click=cancel_workout_form, bgcolor=ft.Colors.GREY),
                ft.ElevatedButton("Salvar", on_click=save_workout_clicked)
            ], alignment=ft.MainAxisAlignment.CENTER)
        ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    
    def build_add_workout_view():
        """Constrói a view para adicionar um novo treino."""
        add_workout_container.controls = [_build_workout_form()]

    def build_edit_workout_view(workout_data: dict):
        """Constrói a view para editar um treino existente."""
        app_state.editing_workout_id = workout_data.get("id")
        edit_workout_container.controls = [_build_workout_form(workout_data)]

    async def build_workouts_view():
        """Constrói a view de treinos com o calendário interativo."""
        month_label = ft.Text(weight=ft.FontWeight.BOLD, size=18)
        calendar_grid = ft.GridView(expand=False, runs_count=7, spacing=5, run_spacing=5)
        workouts_list = ft.ListView(expand=True, spacing=10)
        monthly_colors = {}
        async def _get_workout_colors_by_day(year: int, month: int) -> dict:
            start = datetime.date(year, month, 1)
            _, num_days = calendar.monthrange(year, month)
            end = datetime.date(year, month, num_days)
            colors_map = {}
            with sqlite3.connect("evorun_local.db") as con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute(
                    "SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 0 AND date(workout_date) BETWEEN date(?) AND date(?) ORDER BY workout_date",
                    (app_state.user_profile['email'], start.isoformat(), end.isoformat())
                )
                for row in cur.fetchall():
                    w = dict(row)
                    day_num = datetime.datetime.fromisoformat(w['workout_date']).day
                    color = WORKOUT_VISUALS[w['workout_type']]['color']
                    if day_num not in colors_map:
                        colors_map[day_num] = []
                    if color not in colors_map[day_num]:
                        colors_map[day_num].append(color)
            return colors_map
        def update_calendar(year, month, workout_colors: dict):
            month_label.value = f"{calendar.month_name[month]} {year}"
            cal = calendar.monthcalendar(year, month)
            calendar_grid.controls.clear()
            for day_name in ["S", "T", "Q", "Q", "S", "S", "D",]:
                calendar_grid.controls.append(ft.Container(ft.Text(day_name, text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.BOLD)))
            for week in cal:
                for day in week:
                    if day == 0:
                        calendar_grid.controls.append(ft.Container())
                    else:
                        is_selected = datetime.date(year, month, day) == app_state.current_calendar_date
                        day_container = ft.Container(
                            content=ft.Text(str(day), text_align=ft.TextAlign.CENTER),
                            border_radius=100, ink=True,
                            on_click=lambda _, d=day: select_date(d),
                            alignment=ft.alignment.center
                        )
                        colors_for_day = workout_colors.get(day, [])
                        if is_selected:
                            day_container.bgcolor = ft.Colors.BLUE_700
                        elif not colors_for_day:
                            day_container.bgcolor = ft.Colors.RED_900
                        elif len(colors_for_day) == 1:
                            day_container.bgcolor = colors_for_day[0]
                        else:
                            day_container.gradient = ft.LinearGradient(
                                begin=ft.alignment.top_left,
                                end=ft.alignment.bottom_right,
                                colors=colors_for_day
                            )
                        calendar_grid.controls.append(day_container)
            page.update()
        def update_workouts_list_for_date():
            workouts_list.controls.clear()
            selected_date_str = app_state.current_calendar_date.isoformat()
            with sqlite3.connect("evorun_local.db") as con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute(
                    "SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 0 AND workout_date LIKE ? ORDER BY workout_date DESC",
                    (app_state.user_profile['email'], f"{selected_date_str}%")
                )
                workouts_for_day = [dict(row) for row in cur.fetchall()]
            if not workouts_for_day:
                workouts_list.controls.append(ft.Text("Nenhum treino registrado para este dia.", italic=True))
            else:
                for w in workouts_for_day:
                    visuals = WORKOUT_VISUALS.get(w['workout_type'])
                    description = ""
                    if w['workout_type'] == 'weightlifting':
                        details = json.loads(w.get('details', '{}'))
                        weight = details.get('weight_kg', 0.0)
                        description = f"Carga Total: {weight} kg"
                    elif w['workout_type'] == 'stairs':
                        details = json.loads(w.get('details', '{}'))
                        steps = details.get('steps')
                        if steps:
                            description = f"{w.get('duration_minutes', 0)} min / {steps} degraus"
                        else:
                            description = f"{w.get('duration_minutes', 0)} min"
                    else:
                        description = f"{w.get('duration_minutes', 0)} min"
                        if w.get('distance_km'):
                            description += f" | {w.get('distance_km')} km"
                            if w['workout_type'] in ['running', 'cycling']:
                                details = json.loads(w.get('details', '{}'))
                                elevation = details.get('elevation_level', 0)
                                description += f"\n{ (w.get('duration_minutes', 0) / w.get('distance_km')):.2f} min/km | { (w.get('distance_km') / (w.get('duration_minutes', 0) / 60)):.2f} km/h"
                    async def go_to_edit(e):
                        workout_data = e.control.data
                        build_edit_workout_view(workout_data)
                        await show_view(edit_workout_container)
                    def open_delete_dialog(workout_data):
                        delete_bs.content = ft.Container(
                            padding=20,
                            content=ft.Column([
                                ft.Text("Confirmar Exclusão", size=20, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Tem certeza que deseja excluir o treino de {visuals['name']}?"),
                                ft.Row([
                                    ft.ElevatedButton("Cancelar", on_click=close_bs),
                                    ft.ElevatedButton("Excluir", on_click=delete_workout_confirmed, color="white", bgcolor="red")
                                ], alignment=ft.MainAxisAlignment.END)
                            ])
                        )
                        delete_bs.data = {"local_id": workout_data["id"]}
                        delete_bs.open = True
                        page.update()
                    workouts_list.controls.append(
                        ft.Card(
                            content=ft.ListTile(
                                leading=ft.Icon(visuals['icon'], color=visuals['color']),
                                title=ft.Text(visuals['name'], weight=ft.FontWeight.BOLD, color=visuals['color']),
                                subtitle=ft.Text(description),
                                trailing=ft.PopupMenuButton(
                                    icon=ft.Icons.MORE_VERT,
                                    items=[
                                        ft.PopupMenuItem(text="Editar", icon=ft.Icons.EDIT, on_click=go_to_edit, data=w),
                                        ft.PopupMenuItem(text="Excluir", icon=ft.Icons.DELETE_FOREVER, on_click=lambda _, wd=w: open_delete_dialog(wd)),
                                    ]
                                )
                            )
                        )
                    )
            page.update()
        def select_date(day: int):
            current = app_state.current_calendar_date
            app_state.current_calendar_date = datetime.date(current.year, current.month, day)
            update_calendar(current.year, current.month, monthly_colors)
            update_workouts_list_for_date()
        async def change_month(delta: int):
            nonlocal monthly_colors
            current = app_state.current_calendar_date
            new_month, new_year = (current.month + delta, current.year)
            if new_month > 12: new_month, new_year = 1, new_year + 1
            elif new_month < 1: new_month, new_year = 12, new_year - 1
            _, last_day = calendar.monthrange(new_year, new_month)
            new_day = min(current.day, last_day)
            app_state.current_calendar_date = datetime.date(new_year, new_month, new_day)
            monthly_colors = await _get_workout_colors_by_day(new_year, new_month)
            update_calendar(new_year, new_month, monthly_colors)
            update_workouts_list_for_date()
        async def go_to_today(e):
            nonlocal monthly_colors
            today = datetime.date.today()
            app_state.current_calendar_date = today
            monthly_colors = await _get_workout_colors_by_day(today.year, today.month)
            update_calendar(today.year, today.month, monthly_colors)
            update_workouts_list_for_date()
        async def go_to_prev_month(e): await change_month(-1)
        async def go_to_next_month(e): await change_month(1)
        async def go_to_add_workout(e): await show_view(add_workout_container)
        workouts_container.controls = [
            ft.Row([
                ft.IconButton(ft.Icons.TODAY, on_click=go_to_today, tooltip="Hoje"),
                ft.Container(content=month_label, expand=True, alignment=ft.alignment.center),
                ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=go_to_prev_month),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=go_to_next_month),
            ], alignment=ft.MainAxisAlignment.CENTER),
            calendar_grid, ft.Divider(),
            ft.Row([
                ft.Text("Treinos do Dia", weight=ft.FontWeight.BOLD, expand=True),
                ft.FloatingActionButton(icon=ft.Icons.ADD, on_click=go_to_add_workout, tooltip="Adicionar treino")
            ]),
            workouts_list
        ]
        today = app_state.current_calendar_date
        monthly_colors = await _get_workout_colors_by_day(today.year, today.month)
        update_calendar(today.year, today.month, monthly_colors)
        update_workouts_list_for_date()

    # --- Gerenciador de Views ---
    async def show_view(view_to_show):
        """Gerencia qual tela (container) é exibida ao usuário, reconstruindo-a se necessário."""
        if view_to_show == dashboard_container: await build_dashboard_view()
        elif view_to_show == profile_container: build_profile_view()
        elif view_to_show == onboarding_container: build_onboarding_view()
        elif view_to_show == edit_profile_container: build_edit_profile_view()
        elif view_to_show == workouts_container: await build_workouts_view()
        elif view_to_show == add_workout_container: build_add_workout_view()
        
        for view in all_views:
            view.visible = (view == view_to_show)
        
        navigation_bar.visible = view_to_show not in [login_container, onboarding_container]
        page.update()

    # --- Barra de Navegação e Inicialização da Aplicação ---
    async def navigation_tapped(e):
        """Lida com os cliques na barra de navegação inferior."""
        selected_index = e.control.selected_index
        navigation_bar.selected_index = selected_index
        if selected_index == 0: await show_view(dashboard_container)
        elif selected_index == 1: await show_view(workouts_container)
        elif selected_index == 2: await show_view(profile_container)
        elif selected_index == 3: await logout()
    
    navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Início"),
            ft.NavigationBarDestination(icon=ft.Icons.FITNESS_CENTER_OUTLINED, selected_icon=ft.Icons.FITNESS_CENTER, label="Treinos"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON_OUTLINED, selected_icon=ft.Icons.PERSON, label="Perfil"),
            ft.NavigationBarDestination(icon=ft.Icons.LOGOUT, label="Sair"),
        ],
        on_change=navigation_tapped,
        visible=False, selected_index=0
    )
    
    def on_window_event(e):
        if e.data == "resize":
            print("Janela redimensionada!")
            pass
    
    # --- Lógica de Inicialização ---
    init_local_db()
    
    page.add(
        ft.AppBar(title=ft.Text("EvoRun"), bgcolor=APPBAR_BGCOLOR, center_title=True),
        ft.Container(
            content=ft.Stack(all_views),
            expand=True, alignment=ft.alignment.top_center
        ),
        navigation_bar
    )
    
    page.window.on_event = on_window_event
    
    remembered_email = await page.client_storage.get_async("remembered_email")
    if remembered_email:
        email_field.value = remembered_email
        remember_me_checkbox.value = True
        
    remembered_password = await page.client_storage.get_async("remembered_password")
    if remembered_password:
        password_field.value = remembered_password
    
    page.update()

# --- Ponto de Entrada da Aplicação ---
ft.app(target=main, view=ft.AppView.FLET_APP)
