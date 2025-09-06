import flet as ft
import httpx
import sqlite3
import datetime
from functools import partial
import calendar

# Imports para o gráfico
import matplotlib
import matplotlib.pyplot as plt
from flet.matplotlib_chart import MatplotlibChart

# Configura o matplotlib para não usar um backend de UI interativo, essencial para o Flet
matplotlib.use("svg")

API_URL = "http://127.0.0.1:8000"
APPBAR_BGCOLOR = ft.Colors.BLUE_800

# --- Lógica do Banco de Dados Local ---

def init_local_db():
    """Inicializa o banco de dados SQLite local com as tabelas necessárias."""
    with sqlite3.connect("evorun_local.db") as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER UNIQUE,
                user_email TEXT NOT NULL,
                distance_km REAL NOT NULL,
                duration_minutes INTEGER NOT NULL,
                elevation_level INTEGER NOT NULL,
                workout_date TEXT NOT NULL,
                synced INTEGER DEFAULT 0,
                to_be_deleted INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                email TEXT PRIMARY KEY,
                full_name TEXT,
                age INTEGER,
                weight_kg INTEGER,
                height_cm INTEGER,
                training_days_per_week INTEGER,
                synced INTEGER DEFAULT 1
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
                INSERT INTO workouts (api_id, user_email, distance_km, duration_minutes, elevation_level, workout_date, synced)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(api_id) DO UPDATE SET
                    distance_km=excluded.distance_km,
                    duration_minutes=excluded.duration_minutes,
                    elevation_level=excluded.elevation_level,
                    workout_date=excluded.workout_date,
                    synced=1
            """, (
                workout['id'], user_email, workout['distance_km'],
                workout['duration_minutes'], workout['elevation_level'], workout['workout_date']
            ))
        con.commit()
    print(f"{len(workouts_from_api)} treinos sincronizados do backend para o local.")

class AppState:
    """Uma classe para armazenar o estado da aplicação."""
    def __init__(self):
        self.token = None
        self.user_profile = {}
        self.editing_workout_id = None
        self.selected_calendar_date = datetime.date.today()

async def main(page: ft.Page):
    """Função principal que constrói e gerencia a interface do aplicativo."""
    page.title = "EvoRun"
    page.window_width = 400
    page.window_height = 850
    page.bgcolor = ft.Colors.BLUE_GREY_900
    
    app_state = AppState()

    # --- Lógica de Sincronização ---
    async def sync_local_changes_to_backend():
        """Verifica alterações locais e as envia para o backend."""
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
                try:
                    payload = {k: v for k, v in profile_data.items() if k not in ['email', 'synced']}
                    response = await api_call("PUT", "/api/v1/users/me/profile", json=payload)
                    if response.status_code == 200:
                        save_profile_locally(response.json(), synced=1)
                        print("Perfil sincronizado com sucesso.")
                except httpx.ConnectError:
                    print("Não foi possível sincronizar o perfil. Backend offline.")

            cur.execute("SELECT * FROM workouts WHERE user_email = ? AND synced = 0 AND to_be_deleted = 0", (app_state.user_profile['email'],))
            unsynced_workouts = cur.fetchall()
            if unsynced_workouts:
                print(f"Enviando {len(unsynced_workouts)} treinos não sincronizados...")
                for workout_row in unsynced_workouts:
                    workout = dict(workout_row)
                    workout_data = {
                        "distance_km": workout['distance_km'], 
                        "duration_minutes": workout['duration_minutes'], 
                        "elevation_level": workout['elevation_level'],
                        "workout_date": workout['workout_date']
                    }
                    try:
                        endpoint = f"/api/v1/workouts/{workout['api_id']}" if workout.get('api_id') else "/api/v1/workouts/"
                        method = "PUT" if workout.get('api_id') else "POST"
                        response = await api_call(method, endpoint, json=workout_data)
                        if response.status_code in [200, 201]:
                            api_id = response.json().get("id")
                            cur.execute("UPDATE workouts SET synced = 1, api_id = ? WHERE id = ?", (api_id, workout['id']))
                            con.commit()
                            print(f"Treino local ID {workout['id']} sincronizado.")
                    except httpx.ConnectError:
                        print("Não foi possível sincronizar treinos. Backend offline.")
                        break
            
            cur.execute("SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 1", (app_state.user_profile['email'],))
            workouts_to_delete = cur.fetchall()
            if workouts_to_delete:
                print(f"Enviando {len(workouts_to_delete)} exclusões de treinos...")
                for workout_row in workouts_to_delete:
                    workout = dict(workout_row)
                    if workout.get('api_id'):
                        try:
                            response = await api_call("DELETE", f"/api/v1/workouts/{workout['api_id']}")
                            if response.status_code in [204, 404]:
                                cur.execute("DELETE FROM workouts WHERE id = ?", (workout['id'],))
                                con.commit()
                                print(f"Treino ID {workout['id']} excluído permanentemente.")
                        except httpx.ConnectError:
                            print("Não foi possível sincronizar exclusões. Backend offline.")
                            break
                    else:
                        cur.execute("DELETE FROM workouts WHERE id = ?", (workout['id'],))
                        con.commit()
                        print(f"Treino local ID {workout['id']} (nunca sincronizado) excluído permanentemente.")

    # --- Lógica de API ---
    async def api_call(method, endpoint, data=None, json=None, headers=None):
        """Função central para fazer chamadas à API do backend."""
        auth_headers = {}
        if app_state.token: auth_headers["Authorization"] = f"Bearer {app_state.token}"
        if headers: auth_headers.update(headers)
        async with httpx.AsyncClient() as client:
            if method == "POST": return await client.post(f"{API_URL}{endpoint}", data=data, json=json, headers=auth_headers)
            elif method == "GET": return await client.get(f"{API_URL}{endpoint}", headers=auth_headers)
            elif method == "PUT": return await client.put(f"{API_URL}{endpoint}", json=json, headers=auth_headers)
            elif method == "DELETE": return await client.delete(f"{API_URL}{endpoint}", headers=auth_headers)

    # --- Diálogo de Confirmação (BottomSheet) ---
    async def delete_workout_confirmed(e):
        """Marca um treino para exclusão e atualiza a UI."""
        local_id_to_delete = delete_bs.data.get("local_id")
        
        with sqlite3.connect("evorun_local.db") as con:
            cur = con.cursor()
            cur.execute("UPDATE workouts SET to_be_deleted = 1, synced = 0 WHERE id = ?", (local_id_to_delete,))
            con.commit()
        print(f"Treino local ID {local_id_to_delete} marcado para exclusão.")
        
        close_bs()
        await show_view(workouts_container)

    def close_bs(e=None):
        """Fecha o BottomSheet."""
        delete_bs.open = False
        page.update()

    delete_bs = ft.BottomSheet(ft.Container(), on_dismiss=close_bs)

    # --- Controles da UI ---
    email_field = ft.TextField(label="E-mail", width=300, keyboard_type=ft.KeyboardType.EMAIL, border_color=ft.Colors.BLUE_GREY_400)
    password_field = ft.TextField(label="Senha", width=300, password=True, can_reveal_password=True, border_color=ft.Colors.BLUE_GREY_400)
    remember_me_checkbox = ft.Checkbox(label="Lembrar-me")
    
    # --- Funções de Evento ---
    async def login_clicked(e):
        """Lida com a lógica de login online e offline."""
        loading_indicator_login.visible = True
        login_button.disabled = True
        error_text_login.value = ""
        page.update()
        
        try:
            response = await api_call("POST", "/api/v1/login/token", data={'username': email_field.value, 'password': password_field.value})
            if response.status_code == 200:
                app_state.token = response.json().get("access_token")
                user_response = await api_call("GET", "/api/v1/users/me/")
                
                if user_response.status_code == 200:
                    app_state.user_profile = user_response.json()
                    await sync_local_changes_to_backend()

                    final_user_response = await api_call("GET", "/api/v1/users/me/")
                    app_state.user_profile = final_user_response.json()
                    save_profile_locally(app_state.user_profile, synced=1)

                    workouts_response = await api_call("GET", "/api/v1/workouts/")
                    if workouts_response.status_code == 200:
                        sync_workouts_from_api(app_state.user_profile['email'], workouts_response.json())
                    
                    if remember_me_checkbox.value:
                        await page.client_storage.set_async("remembered_email", email_field.value)
                        await page.client_storage.set_async("remembered_password", password_field.value)
                    
                    if not app_state.user_profile.get("full_name"): await show_view(onboarding_container)
                    else: await show_view(dashboard_container)
                else: error_text_login.value = "Erro ao buscar perfil."
            else: error_text_login.value = "E-mail ou senha incorretos."
        except httpx.ConnectError:
            print("Conexão falhou. Tentando login offline.")
            remembered_email = await page.client_storage.get_async("remembered_email")
            remembered_password = await page.client_storage.get_async("remembered_password")

            if (remembered_email and remembered_password and
                email_field.value.strip() == remembered_email and
                password_field.value == remembered_password):
                local_profile = load_profile_locally(email_field.value)
                if local_profile:
                    app_state.user_profile = local_profile
                    await show_view(dashboard_container)
                else: error_text_login.value = "Perfil local não encontrado."
            else: error_text_login.value = "Credenciais inválidas para login offline."
        
        loading_indicator_login.visible = False
        login_button.disabled = False
        page.update()

    async def logout(e=None):
        """Lida com a lógica de logout."""
        app_state.token = None
        app_state.user_profile = {}
        await show_view(login_container)

    # --- Containers de Tela ---
    login_button = ft.ElevatedButton("Entrar", width=300, on_click=login_clicked, bgcolor=ft.Colors.INDIGO, color=ft.Colors.WHITE)
    error_text_login = ft.Text(value="", color=ft.Colors.RED_500)
    loading_indicator_login = ft.ProgressRing(visible=False)
    login_container = ft.Column([ft.Text("EvoRun", size=32, weight=ft.FontWeight.BOLD), email_field, password_field, remember_me_checkbox, login_button, loading_indicator_login, error_text_login], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, visible=True)
    onboarding_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    dashboard_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    profile_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    edit_profile_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    workouts_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
    add_workout_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    edit_workout_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # --- Funções de Construção de Views ---
    async def build_dashboard_view():
        """Constrói o conteúdo da tela de dashboard, incluindo os gráficos de evolução."""
        user_name = app_state.user_profile.get("full_name", "Usuário")
        
        velocity_chart = ft.Container(expand=True, alignment=ft.alignment.center)
        distance_chart = ft.Container(expand=True, alignment=ft.alignment.center)
        pace_chart = ft.Container(expand=True, alignment=ft.alignment.center)

        def create_chart(title, y_label, x_labels, y_data):
            """Função auxiliar para criar um gráfico Matplotlib estilizado."""
            plt.close('all')
            fig, ax = plt.subplots(figsize=(6, 4))
            x_axis = range(len(x_labels))
            ax.plot(x_axis, y_data, marker='o', linestyle='-', color='#8561c5')
            
            ax.set_xticks(x_axis)
            ax.set_xticklabels(x_labels, rotation=45, ha="right")
            
            fig.patch.set_facecolor('#202429')
            ax.set_facecolor('#292e35')
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            ax.spines['bottom'].set_color('white')
            ax.spines['left'].set_color('white')
            ax.spines['top'].set_color('none')
            ax.spines['right'].set_color('none')
            
            ax.set_title(title, color="white")
            ax.set_ylabel(y_label, color="white")
            ax.grid(True, linestyle='--', linewidth=0.5, color='grey')
            plt.tight_layout()
            return MatplotlibChart(fig, expand=True)

        async def update_all_charts(filter_days: int):
            """Busca dados, filtra e atualiza o conteúdo de todos os gráficos."""
            with sqlite3.connect("evorun_local.db") as con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute("SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 0 ORDER BY workout_date ASC", (app_state.user_profile['email'],))
                all_workouts = [dict(row) for row in cur.fetchall()]

            now = datetime.datetime.now()
            start_date = now - datetime.timedelta(days=filter_days)
            workouts = [w for w in all_workouts if datetime.datetime.fromisoformat(w['workout_date']) >= start_date]

            if len(workouts) < 2:
                no_data_text = ft.Text("Registre pelo menos dois treinos neste período para ver os gráficos!", italic=True, color=ft.Colors.BLUE_GREY_300)
                velocity_chart.content = distance_chart.content = pace_chart.content = no_data_text
            else:
                dates = [datetime.datetime.fromisoformat(w['workout_date']) for w in workouts]
                x_labels = [d.strftime('%d/%m') for d in dates]
                distances = [w['distance_km'] for w in workouts]
                durations = [w['duration_minutes'] for w in workouts]
                
                velocities = [d / (t / 60) if t > 0 else 0 for d, t in zip(distances, durations)]
                paces = [t / d if d > 0 else 0 for d, t in zip(durations, distances)]
                
                velocity_chart.content = create_chart("Evolução da Velocidade", "Velocidade (km/h)", x_labels, velocities)
                distance_chart.content = create_chart("Evolução da Distância", "Distância (km)", x_labels, distances)
                pace_chart.content = create_chart("Evolução do Pace", "Pace (min/km)", x_labels, paces)
            
            page.update()

        async def filter_changed(e):
            """Callback para quando o filtro de período é alterado."""
            period_map = {"7D": 7, "30D": 30, "90D": 90, "ANO": 365}
            clean_key = e.data.strip('[]"')
            await update_all_charts(period_map[clean_key])

        filter_buttons = ft.SegmentedButton(
            on_change=filter_changed,
            selected={"30D"},
            segments=[ft.Segment(value="7D", label=ft.Text("7d")), ft.Segment(value="30D", label=ft.Text("30d")), ft.Segment(value="90D", label=ft.Text("90d")), ft.Segment(value="ANO", label=ft.Text("Ano"))]
        )
        
        tabs = ft.Tabs(
            selected_index=0, animation_duration=300, tab_alignment=ft.TabAlignment.CENTER,
            tabs=[ft.Tab(text="Velocidade", content=velocity_chart), ft.Tab(text="Distância", content=distance_chart), ft.Tab(text="Pace", content=pace_chart)],
            expand=1,
        )

        dashboard_container.controls = [ft.Text(f"Olá, {user_name}!", size=24, weight=ft.FontWeight.BOLD), ft.Text("Sua evolução recente:"), filter_buttons, tabs]
        await update_all_charts(30)

    def build_profile_view():
        """Constrói o conteúdo da tela de perfil."""
        async def go_to_edit_profile(e): await show_view(edit_profile_container)
        profile_container.controls = [ft.Text("Perfil do Usuário", size=24, weight=ft.FontWeight.BOLD), ft.Text(f"Nome: {app_state.user_profile.get('full_name', '')}"), ft.Text(f"E-mail: {app_state.user_profile.get('email', '')}"), ft.Text(f"Idade: {app_state.user_profile.get('age', '')} anos"), ft.ElevatedButton("Editar Perfil", on_click=go_to_edit_profile)]

    def build_onboarding_view():
        """Constrói o conteúdo da tela de onboarding."""
        name_field = ft.TextField(label="Nome Completo", width=300)
        age_field = ft.TextField(label="Idade", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        weight_field = ft.TextField(label="Peso (kg)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        height_field = ft.TextField(label="Altura (cm)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        days_field = ft.TextField(label="Dias de treino/semana", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        error_text_onboarding = ft.Text(value="", color=ft.Colors.RED_500)

        async def save_profile(e):
            if app_state.token: await sync_local_changes_to_backend()
            try:
                profile_data = { "email": app_state.user_profile.get("email"), "full_name": name_field.value, "age": int(age_field.value), "weight_kg": int(weight_field.value), "height_cm": int(height_field.value), "training_days_per_week": int(days_field.value) }
                app_state.user_profile.update(profile_data)
                save_profile_locally(app_state.user_profile, synced=0)
                try:
                    response = await api_call("PUT", "/api/v1/users/me/profile", json=profile_data)
                    if response.status_code == 200:
                        app_state.user_profile = response.json()
                        save_profile_locally(app_state.user_profile, synced=1)
                except httpx.ConnectError: print("Backend offline. Perfil salvo localmente.")
                await show_view(dashboard_container)
            except (ValueError, TypeError): error_text_onboarding.value = "Por favor, preencha todos os campos."; page.update()
        
        onboarding_container.controls = [ft.Column([name_field, age_field, weight_field, height_field, days_field, ft.ElevatedButton("Salvar e Continuar", on_click=save_profile), error_text_onboarding], scroll=ft.ScrollMode.AUTO, spacing=15, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)]
    
    def build_edit_profile_view():
        """Constrói o conteúdo da tela de edição de perfil."""
        name_edit_field = ft.TextField(label="Nome Completo", value=app_state.user_profile.get('full_name', ''), width=300)
        age_edit_field = ft.TextField(label="Idade", value=str(app_state.user_profile.get('age', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        weight_edit_field = ft.TextField(label="Peso (kg)", value=str(app_state.user_profile.get('weight_kg', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        height_edit_field = ft.TextField(label="Altura (cm)", value=str(app_state.user_profile.get('height_cm', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        days_edit_field = ft.TextField(label="Dias de treino/semana", value=str(app_state.user_profile.get('training_days_per_week', '')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        
        async def update_profile_clicked(e):
            if app_state.token: await sync_local_changes_to_backend()
            updated_data = {"full_name": name_edit_field.value, "age": int(age_edit_field.value), "weight_kg": int(weight_edit_field.value), "height_cm": int(height_edit_field.value), "training_days_per_week": int(days_edit_field.value)}
            app_state.user_profile.update(updated_data)
            save_profile_locally(app_state.user_profile, synced=0)
            try:
                response = await api_call("PUT", "/api/v1/users/me/profile", json=updated_data)
                if response.status_code == 200:
                    app_state.user_profile = response.json()
                    save_profile_locally(app_state.user_profile, synced=1)
            except httpx.ConnectError: print("Backend offline. Perfil atualizado localmente.")
            await show_view(profile_container)

        edit_profile_container.controls = [name_edit_field, age_edit_field, weight_edit_field, height_edit_field, days_edit_field, ft.ElevatedButton("Salvar Alterações", on_click=update_profile_clicked)]

    def build_add_workout_view():
        """Constrói o conteúdo da tela de adicionar treino."""
        distance_field = ft.TextField(label="Distância (km)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        duration_field = ft.TextField(label="Duração (minutos)", width=300, keyboard_type=ft.KeyboardType.NUMBER)
        elevation_field = ft.TextField(label="Nível de Elevação", width=300, keyboard_type=ft.KeyboardType.NUMBER, value="0")
        
        async def save_workout_clicked(e):
            if app_state.token: await sync_local_changes_to_backend()
            try:
                workout_data = {"distance_km": float(distance_field.value), "duration_minutes": int(duration_field.value), "elevation_level": int(elevation_field.value)}
                with sqlite3.connect("evorun_local.db") as con:
                    cur = con.cursor()
                    cur.execute("INSERT INTO workouts (user_email, distance_km, duration_minutes, elevation_level, workout_date) VALUES (?, ?, ?, ?, ?)", (app_state.user_profile['email'], workout_data["distance_km"], workout_data["duration_minutes"], workout_data["elevation_level"], datetime.datetime.now().isoformat()))
                    con.commit()
                    local_workout_id = cur.lastrowid
                print(f"Treino salvo localmente com ID: {local_workout_id}")
                try:
                    response = await api_call("POST", "/api/v1/workouts/", json=workout_data)
                    if response.status_code == 201:
                        api_id = response.json().get("id")
                        with sqlite3.connect("evorun_local.db") as con:
                            cur = con.cursor()
                            cur.execute("UPDATE workouts SET synced = 1, api_id = ? WHERE id = ?", (api_id, local_workout_id))
                            con.commit()
                except httpx.ConnectError: print("Backend offline. Treino salvo para sincronização futura.")
                await show_view(workouts_container)
            except (ValueError, TypeError): print("Erro: dados inválidos")

        add_workout_container.controls = [distance_field, duration_field, elevation_field, ft.ElevatedButton("Salvar Treino", on_click=save_workout_clicked)]

    def build_edit_workout_view(workout_data: dict):
        """Constrói o conteúdo da tela de edição de treino."""
        date_button_text = ft.Text(datetime.datetime.fromisoformat(workout_data['workout_date']).strftime('%d/%m/%Y'))
        time_button_text = ft.Text(datetime.datetime.fromisoformat(workout_data['workout_date']).strftime('%H:%M'))
        
        date_picker = ft.DatePicker()
        time_picker = ft.TimePicker()
        page.overlay.extend([date_picker, time_picker])
        
        def handle_date_change(e):
            date_button_text.value = date_picker.value.strftime('%d/%m/%Y')
            page.update()

        def handle_time_change(e):
            time_button_text.value = time_picker.value.strftime('%H:%M')
            page.update()
            
        date_picker.on_change = handle_date_change
        time_picker.on_change = handle_time_change

        distance_edit_field = ft.TextField(label="Distância (km)", value=str(workout_data.get('distance_km')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        duration_edit_field = ft.TextField(label="Duração (minutos)", value=str(workout_data.get('duration_minutes')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        elevation_edit_field = ft.TextField(label="Nível de Elevação", value=str(workout_data.get('elevation_level')), width=300, keyboard_type=ft.KeyboardType.NUMBER)

        async def update_workout_clicked(e):
            if app_state.token: await sync_local_changes_to_backend()
            
            new_date = datetime.datetime.strptime(date_button_text.value, '%d/%m/%Y').date()
            new_time = datetime.datetime.strptime(time_button_text.value, '%H:%M').time()
            new_datetime = datetime.datetime.combine(new_date, new_time).isoformat()

            updated_data = {"distance_km": float(distance_edit_field.value), "duration_minutes": int(duration_edit_field.value), "elevation_level": int(elevation_edit_field.value), "workout_date": new_datetime}
            workout_id = app_state.editing_workout_id
            with sqlite3.connect("evorun_local.db") as con:
                cur = con.cursor()
                cur.execute("UPDATE workouts SET distance_km = ?, duration_minutes = ?, elevation_level = ?, workout_date = ?, synced = 0 WHERE id = ?", (updated_data['distance_km'], updated_data['duration_minutes'], updated_data['elevation_level'], updated_data['workout_date'], workout_id))
                con.commit()
            
            try:
                with sqlite3.connect("evorun_local.db") as con:
                    cur = con.cursor()
                    cur.execute("SELECT api_id FROM workouts WHERE id = ?", (workout_id,))
                    res = cur.fetchone()
                    api_id = res[0] if res else None

                if api_id:
                    response = await api_call("PUT", f"/api/v1/workouts/{api_id}", json=updated_data)
                    if response.status_code == 200:
                        with sqlite3.connect("evorun_local.db") as con:
                            cur = con.cursor()
                            cur.execute("UPDATE workouts SET synced = 1 WHERE id = ?", (workout_id,))
                            con.commit()
            except httpx.ConnectError: print("Backend offline. Edição salva para sincronização futura.")
            await show_view(workouts_container)
        
        async def go_to_workouts_view(e): await show_view(workouts_container)
        
        def open_date_picker(e):
            page.open(date_picker)

        def open_time_picker(e):
            page.open(time_picker)

        edit_workout_container.controls = [
            ft.Row([ft.ElevatedButton(content=date_button_text, on_click=open_date_picker), ft.ElevatedButton(content=time_button_text, on_click=open_time_picker)], alignment=ft.MainAxisAlignment.CENTER),
            distance_edit_field, duration_edit_field, elevation_edit_field, 
            ft.ElevatedButton("Salvar Alterações", on_click=update_workout_clicked), 
            ft.ElevatedButton("Cancelar", on_click=go_to_workouts_view)
        ]

    async def build_workouts_view():
        """Constrói o conteúdo da tela de treinos com o novo layout."""
        workouts_list_column = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)
        
        async def go_to_add_workout(e): await show_view(add_workout_container)
        async def go_to_edit_workout(e):
            workout = e.control.data
            app_state.editing_workout_id = workout.get('id')
            build_edit_workout_view(workout) 
            await show_view(edit_workout_container)

        def open_delete_dialog(e):
            workout_to_delete = e.control.data
            delete_bs.data = {"local_id": workout_to_delete.get("id")}
            delete_bs.content = ft.Container(ft.Column([ft.Text("Confirmar Exclusão", size=18, weight=ft.FontWeight.BOLD), ft.Text("Você tem certeza de que deseja excluir este treino?"), ft.Row([ft.TextButton("Não", on_click=close_bs), ft.FilledButton("Sim, Excluir", on_click=delete_workout_confirmed)], alignment=ft.MainAxisAlignment.END)], tight=True), padding=20)
            delete_bs.open = True
            page.update()

        def build_workout_list(selected_date: datetime.date):
            """Filtra e constrói a lista de treinos para uma data específica."""
            workouts_list_column.controls.clear()
            with sqlite3.connect("evorun_local.db") as con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute("SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 0 ORDER BY workout_date DESC", (app_state.user_profile['email'],))
                all_workouts = [dict(row) for row in cur.fetchall()]
            
            workouts_in_day = [w for w in all_workouts if datetime.datetime.fromisoformat(w['workout_date']).date() == selected_date]

            if not workouts_in_day:
                workouts_list_column.controls.append(ft.Text("Nenhum treino registrado neste dia.", italic=True, color=ft.Colors.BLUE_GREY_300, text_align=ft.TextAlign.CENTER))
            else:
                for workout in workouts_in_day:
                    workouts_list_column.controls.append(
                        ft.Container(
                            ft.Row([
                                ft.Column([ft.Text(f"{datetime.datetime.fromisoformat(workout['workout_date']).strftime('%H:%M')}", weight=ft.FontWeight.BOLD), ft.Text("Corrida", size=12, color=ft.Colors.GREEN_400)]),
                                ft.Column([ft.Text(f"{workout['duration_minutes']} min"), ft.Text("Duração", size=12, color=ft.Colors.BLUE_GREY_300)], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                ft.Column([ft.Text(f"{workout['distance_km']} km"), ft.Text("Distância", size=12, color=ft.Colors.BLUE_GREY_300)], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                ft.Row([ft.IconButton(ft.Icons.EDIT, data=workout, on_click=go_to_edit_workout), ft.IconButton(ft.Icons.DELETE_OUTLINE, data=workout, on_click=open_delete_dialog, icon_color=ft.Colors.RED_400)])
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=15, border_radius=8, bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE10)
                        )
                    )
            page.update()
        
        calendar_view = ft.Column()
        
        def update_calendar(year, month):
            calendar_view.controls.clear()
            month_name = datetime.date(year, month, 1).strftime('%B %Y')
            
            def change_month(e):
                new_month = month + e.control.data
                new_year = year
                if new_month > 12: new_month, new_year = 1, year + 1
                elif new_month < 1: new_month, new_year = 12, year - 1
                update_calendar(new_year, new_month)
                
            def select_date(e):
                app_state.selected_calendar_date = e.control.data
                update_calendar(year, month) # Rebuid calendar to show selection
                build_workout_list(app_state.selected_calendar_date)

            calendar_view.controls.append(
                ft.Row([
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=change_month, data=-1),
                    ft.Text(month_name, expand=True, text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.BOLD),
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=change_month, data=1)
                ])
            )

            with sqlite3.connect("evorun_local.db") as con:
                cur = con.cursor()
                cur.execute("SELECT DISTINCT strftime('%Y-%m-%d', workout_date) FROM workouts WHERE user_email = ? AND to_be_deleted = 0", (app_state.user_profile['email'],))
                workout_days = {datetime.datetime.strptime(row[0], '%Y-%m-%d').date() for row in cur.fetchall()}

            month_matrix = calendar.monthcalendar(year, month)
            for week in month_matrix:
                week_row = ft.Row(alignment=ft.MainAxisAlignment.SPACE_AROUND)
                for day in week:
                    if day == 0:
                        week_row.controls.append(ft.Container(width=32, height=32))
                    else:
                        date_obj = datetime.date(year, month, day)
                        is_selected = date_obj == app_state.selected_calendar_date
                        has_workout = date_obj in workout_days
                        
                        day_button = ft.Container(
                            content=ft.Text(str(day), color=ft.Colors.WHITE if is_selected else ft.Colors.BLACK, weight=ft.FontWeight.BOLD),
                            width=32, height=32,
                            alignment=ft.alignment.center,
                            border_radius=16,
                            bgcolor=ft.Colors.INDIGO_400 if is_selected else (ft.Colors.GREEN_800 if has_workout else ft.Colors.WHITE10),
                            on_click=select_date,
                            data=date_obj
                        )
                        week_row.controls.append(day_button)
                calendar_view.controls.append(week_row)
            page.update()

        workouts_container.controls = [
            ft.FilledButton("Novo Treino", icon="add", on_click=go_to_add_workout), 
            ft.Container(
                content=ft.Column([
                    calendar_view,
                    ft.Divider(),
                    workouts_list_column
                ], expand=True, scroll=ft.ScrollMode.AUTO), # <-- CORREÇÃO DE ROLAGEM
                padding=10, border_radius=8, expand=True
            )
        ]
        
        update_calendar(app_state.selected_calendar_date.year, app_state.selected_calendar_date.month)
        build_workout_list(app_state.selected_calendar_date)

    # --- Gerenciador de Views ---
    async def show_view(view_to_show):
        """Gerencia qual tela é exibida ao usuário."""
        if view_to_show == dashboard_container: await build_dashboard_view()
        elif view_to_show == profile_container: build_profile_view()
        elif view_to_show == onboarding_container: build_onboarding_view()
        elif view_to_show == add_workout_container: build_add_workout_view()
        elif view_to_show == edit_profile_container: build_edit_profile_view()
        elif view_to_show == workouts_container: await build_workouts_view()
        
        navigation_bar.visible = view_to_show not in [login_container, onboarding_container]
        all_containers = [login_container, onboarding_container, dashboard_container, profile_container, add_workout_container, edit_profile_container, workouts_container, edit_workout_container]
        for view in all_containers:
            view.visible = (view == view_to_show)
        page.update()

    # --- Barra de Navegação e Inicialização ---
    async def navigation_tapped(e):
        """Lida com os cliques na barra de navegação."""
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
    
    page.overlay.append(delete_bs) # Adiciona o BottomSheet à página
    page.add(
        ft.AppBar(title=ft.Text("EvoRun"), bgcolor=APPBAR_BGCOLOR),
        ft.Container(
            content=ft.Stack([
                login_container, onboarding_container, dashboard_container, 
                profile_container, add_workout_container, edit_profile_container, 
                workouts_container, edit_workout_container
            ]),
            expand=True,
            alignment=ft.alignment.center
        ),
        navigation_bar
    )
    
    remembered_email = await page.client_storage.get_async("remembered_email")
    if remembered_email:
        email_field.value = remembered_email
        remember_me_checkbox.value = True
        
    remembered_password = await page.client_storage.get_async("remembered_password")
    if remembered_password:
        password_field.value = remembered_password
    
    page.update()

ft.app(target=main, view=ft.AppView.FLET_APP)
