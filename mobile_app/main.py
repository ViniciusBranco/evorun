import flet as ft
import httpx
import sqlite3
import datetime


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
        print("DEBUG: Iniciando sync_local_changes_to_backend...")
        if not app_state.token or not app_state.user_profile.get('email'):
            print("DEBUG: Sincronização abortada: sem token ou perfil de usuário.")
            return

        with sqlite3.connect("evorun_local.db") as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            
            # 1. Sincronizar Perfil
            cur.execute("SELECT * FROM user_profile WHERE email = ? AND synced = 0", (app_state.user_profile['email'],))
            unsynced_profile = cur.fetchone()
            if unsynced_profile:
                profile_data = dict(unsynced_profile)
                print("DEBUG: Enviando perfil não sincronizado...")
                try:
                    payload = {k: v for k, v in profile_data.items() if k not in ['email', 'synced']}
                    response = await api_call("PUT", "/api/v1/users/me/profile", json=payload)
                    if response.status_code == 200:
                        save_profile_locally(response.json(), synced=1)
                        print("DEBUG: Perfil sincronizado com sucesso.")
                except httpx.ConnectError:
                    print("DEBUG: Não foi possível sincronizar o perfil. Backend offline.")

            # 2. Sincronizar Treinos (Criação e Edição)
            cur.execute("SELECT * FROM workouts WHERE user_email = ? AND synced = 0 AND to_be_deleted = 0", (app_state.user_profile['email'],))
            unsynced_workouts = cur.fetchall()
            if unsynced_workouts:
                print(f"DEBUG: Enviando {len(unsynced_workouts)} treinos não sincronizados...")
                for workout_row in unsynced_workouts:
                    workout = dict(workout_row)
                    workout_data = {"distance_km": workout['distance_km'], "duration_minutes": workout['duration_minutes'], "elevation_level": workout['elevation_level']}
                    try:
                        endpoint = f"/api/v1/workouts/{workout['api_id']}" if workout.get('api_id') else "/api/v1/workouts/"
                        method = "PUT" if workout.get('api_id') else "POST"
                        response = await api_call(method, endpoint, json=workout_data)
                        if response.status_code in [200, 201]:
                            api_id = response.json().get("id")
                            cur.execute("UPDATE workouts SET synced = 1, api_id = ? WHERE id = ?", (api_id, workout['id']))
                            con.commit()
                            print(f"DEBUG: Treino local ID {workout['id']} sincronizado.")
                    except httpx.ConnectError:
                        print("DEBUG: Não foi possível sincronizar treinos. Backend offline.")
                        break
            
            # 3. Sincronizar Exclusões de Treinos
            cur.execute("SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 1", (app_state.user_profile['email'],))
            workouts_to_delete = cur.fetchall()
            if workouts_to_delete:
                print(f"DEBUG: Enviando {len(workouts_to_delete)} exclusões de treinos...")
                for workout_row in workouts_to_delete:
                    workout = dict(workout_row)
                    if workout.get('api_id'):
                        try:
                            response = await api_call("DELETE", f"/api/v1/workouts/{workout['api_id']}")
                            if response.status_code in [204, 404]:
                                cur.execute("DELETE FROM workouts WHERE id = ?", (workout['id'],))
                                con.commit()
                                print(f"DEBUG: Treino ID {workout['id']} excluído permanentemente.")
                        except httpx.ConnectError:
                            print("DEBUG: Não foi possível sincronizar exclusões. Backend offline.")
                            break
                    else:
                        cur.execute("DELETE FROM workouts WHERE id = ?", (workout['id'],))
                        con.commit()
                        print(f"DEBUG: Treino local ID {workout['id']} (nunca sincronizado) excluído permanentemente.")

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
    workouts_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    add_workout_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    edit_workout_container = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # --- Funções de Construção de Views ---
    def build_dashboard_view():
        """Constrói o conteúdo da tela de dashboard."""
        user_name = app_state.user_profile.get("full_name", "Usuário")
        dashboard_container.controls = [ft.Text(f"Bem-vindo, {user_name}!", size=24, weight=ft.FontWeight.BOLD)]

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
        distance_edit_field = ft.TextField(label="Distância (km)", value=str(workout_data.get('distance_km')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        duration_edit_field = ft.TextField(label="Duração (minutos)", value=str(workout_data.get('duration_minutes')), width=300, keyboard_type=ft.KeyboardType.NUMBER)
        elevation_edit_field = ft.TextField(label="Nível de Elevação", value=str(workout_data.get('elevation_level')), width=300, keyboard_type=ft.KeyboardType.NUMBER)

        async def update_workout_clicked(e):
            if app_state.token: await sync_local_changes_to_backend()
            updated_data = {"distance_km": float(distance_edit_field.value), "duration_minutes": int(duration_edit_field.value), "elevation_level": int(elevation_edit_field.value)}
            workout_id = app_state.editing_workout_id
            with sqlite3.connect("evorun_local.db") as con:
                cur = con.cursor()
                cur.execute("UPDATE workouts SET distance_km = ?, duration_minutes = ?, elevation_level = ?, synced = 0 WHERE id = ?", (updated_data['distance_km'], updated_data['duration_minutes'], updated_data['elevation_level'], workout_id))
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
        edit_workout_container.controls = [distance_edit_field, duration_edit_field, elevation_edit_field, ft.ElevatedButton("Salvar Alterações", on_click=update_workout_clicked), ft.ElevatedButton("Cancelar", on_click=go_to_workouts_view)]

    async def build_workouts_view():
        """Constrói o conteúdo da tela de treinos."""
        workouts_list = ft.ListView(spacing=10, expand=True)
        async def go_to_add_workout(e): await show_view(add_workout_container)
        async def go_to_edit_workout(e):
            workout = e.control.data
            app_state.editing_workout_id = workout.get('id')
            build_edit_workout_view(workout) 
            await show_view(edit_workout_container)

        def open_delete_dialog(e):
            """Constrói e abre o diálogo de confirmação."""
            workout_to_delete = e.control.data
            delete_bs.data = {"local_id": workout_to_delete.get("id")}
            
            delete_bs.content = ft.Container(
                ft.Column([
                    ft.Text("Confirmar Exclusão", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Você tem certeza de que deseja excluir este treino?"),
                    ft.Row([
                        ft.TextButton("Não", on_click=close_bs),
                        ft.FilledButton("Sim, Excluir", on_click=delete_workout_confirmed),
                    ], alignment=ft.MainAxisAlignment.END),
                ], tight=True),
                padding=20,
            )
            delete_bs.open = True
            page.update()

        workouts_container.controls = [ft.FilledButton("Novo Treino", icon="add", on_click=go_to_add_workout), workouts_list]
        workouts_list.controls.clear()
        
        with sqlite3.connect("evorun_local.db") as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM workouts WHERE user_email = ? AND to_be_deleted = 0 ORDER BY workout_date DESC", (app_state.user_profile['email'],))
            local_workouts = cur.fetchall()

        for workout in local_workouts:
            workout_dict = dict(workout)
            workouts_list.controls.append(ft.Row([ft.Text(f"{datetime.datetime.fromisoformat(workout_dict['workout_date']).strftime('%d/%m/%Y')} - {workout_dict['distance_km']} km em {workout_dict['duration_minutes']} min"), ft.Row([ft.IconButton(ft.Icons.EDIT, data=workout_dict, on_click=go_to_edit_workout), ft.IconButton(ft.Icons.DELETE_OUTLINE, data=workout_dict, on_click=open_delete_dialog, icon_color=ft.Colors.RED_400)])], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        page.update()

    # --- Gerenciador de Views ---
    async def show_view(view_to_show):
        """Gerencia qual tela é exibida ao usuário."""
        if view_to_show == dashboard_container: build_dashboard_view()
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
