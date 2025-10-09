import streamlit as st
import httpx
from typing import Optional, Tuple, Any

API_BASE = "http://api:3000"  # service name in docker network (docker compose network)

st.set_page_config(page_title="Age Groups & Enrollment", page_icon="🗂️", layout="wide")

# -------------- Helpers --------------
def current_auth() -> Optional[Tuple[str, str]]:
    return st.session_state.get("auth")

async def fetch_json(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    auth = kwargs.pop("auth", current_auth())
    try:
        resp = await client.request(method, url, auth=auth, timeout=10, **kwargs)
        if resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json()
        else:
            data = {"raw": resp.text}
        if resp.is_error:
            return False, data, resp.status_code
        return True, data, resp.status_code
    except Exception as e:
        return False, {"error": str(e)}, 0

async def list_age_groups(client):
    return await fetch_json(client, "GET", f"{API_BASE}/api/v1/age-groups")

async def create_age_group(client, name: str, min_age: int, max_age: int):
    payload = {"name": name, "min_age": min_age, "max_age": max_age}
    return await fetch_json(client, "POST", f"{API_BASE}/api/v1/age-groups", json=payload)

async def delete_age_group(client, group_id: str):
    return await fetch_json(client, "DELETE", f"{API_BASE}/api/v1/age-groups/{group_id}")

async def create_enrollment(client, name: str, age: int, cpf: str):
    payload = {"name": name, "age": age, "cpf": cpf}
    return await fetch_json(client, "POST", f"{API_BASE}/api/v1/enrollments", json=payload)

async def get_enrollment_status(client, enrollment_id: str):
    return await fetch_json(client, "GET", f"{API_BASE}/api/v1/enrollments/{enrollment_id}")

# -------------- UI Sections --------------
st.title("🗂️ Age Groups & Enrollment Console")
st.caption("Interface simples em Streamlit para explorar a API (login obrigatório)")

import asyncio

async def validate_credentials(user: str, password: str) -> bool:
    """Realiza uma chamada ao endpoint raiz para validar credenciais Basic Auth."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_BASE}/", auth=(user, password), timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

def logout():
    if "auth" in st.session_state:
        st.session_state.pop("auth")
    st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun()

async def main_ui():
    # Gating de autenticação
    if "auth" not in st.session_state:
        with st.container():
            st.subheader("🔐 Login")
            with st.form("login_form", clear_on_submit=False):
                user = st.text_input("Usuário", key="login_user")
                pwd = st.text_input("Senha", type="password", key="login_pwd")
                submitted = st.form_submit_button("Entrar")
                if submitted:
                    if not user or not pwd:
                        st.warning("Preencha usuário e senha.")
                    else:
                        ok = await validate_credentials(user, pwd)
                        if ok:
                            st.session_state["auth"] = (user, pwd)
                            st.success("Autenticado com sucesso.")
                            st.rerun()
                        else:
                            st.error("Credenciais inválidas ou serviço indisponível.")
        st.stop()

    auth_user = st.session_state.get("auth")[0]
    st.sidebar.markdown(f"**Usuário:** {auth_user}")
    st.sidebar.button("Sair", on_click=logout)

    async with httpx.AsyncClient() as client:
        tabs = st.tabs(["Grupos Etários", "Inscrições", "Status de Inscrição", "Sobre"])

        # ---- Tab Grupos ----
        with tabs[0]:
            st.subheader("Gerenciar Grupos Etários")

            # Carrega grupos existentes uma vez para usar na validação e na listagem
            groups_ok, groups_data, groups_status = await list_age_groups(client)
            if not groups_ok:
                st.error(f"Erro ao carregar grupos ({groups_status}): {groups_data}")

            col_form, col_list = st.columns([1,2])

            # -------- Formulário criação --------
            with col_form:
                st.markdown("**Criar novo grupo**")
                g_name = st.text_input("Nome", key="g_name")
                c1, c2 = st.columns(2)
                with c1:
                    g_min = st.number_input("Idade mínima", min_value=0, max_value=150, value=18, key="g_min")
                with c2:
                    g_max = st.number_input("Idade máxima", min_value=0, max_value=150, value=60, key="g_max")

                # Validações front-end antes do POST
                if g_min > g_max:
                    st.error("Idade mínima não pode ser maior que a máxima.")
                # Verifica sobreposição provável localmente (heurística)
                if groups_ok and isinstance(groups_data, list):
                    overlap_pred = [g for g in groups_data if not (g_min > g['max_age'] or g_max < g['min_age'])]
                    if overlap_pred:
                        with st.expander("Possível sobreposição detectada (pré-validação)", expanded=False):
                            for og in overlap_pred:
                                st.write(f"• {og['name']} ({og['min_age']}-{og['max_age']})")

                if st.button("Criar Grupo", type="primary"):
                    if not g_name:
                        st.warning("Informe um nome para o grupo.")
                    elif g_min > g_max:
                        st.warning("Corrija o intervalo de idades antes de enviar.")
                    else:
                        ok, data, status = await create_age_group(client, g_name, int(g_min), int(g_max))
                        if ok:
                            gid = data.get('id') or data.get('_id')
                            st.success(f"Grupo criado: {gid}")
                            st.session_state.setdefault('created_groups', []).append(gid)
                            st.rerun()
                        else:
                            # Extrai detalhe amigável
                            detail = data.get('detail') if isinstance(data, dict) else data
                            if status == 409:
                                st.error(f"Sobreposição de faixa: {detail}")
                            elif status == 400:
                                st.error(f"Dados inválidos: {detail}")
                            else:
                                st.error(f"Erro ({status}): {detail}")

            # -------- Listagem --------
            with col_list:
                st.markdown("**Grupos Existentes**")
                if groups_ok and isinstance(groups_data, list):
                    if not groups_data:
                        st.info("Nenhum grupo cadastrado ainda.")
                    for g in groups_data:
                        gid = g.get('id') or g.get('_id')
                        label = f"{g.get('name')} ({g.get('min_age')}-{g.get('max_age')})"
                        with st.expander(label):
                            st.json(g)
                            btn_col1, btn_col2 = st.columns([1,3])
                            with btn_col1:
                                if gid and st.button("Excluir", key=f"del_{gid}"):
                                    dok, ddata, dstatus = await delete_age_group(client, gid)
                                    if dok:
                                        st.warning(f"Grupo {gid} removido")
                                    else:
                                        detail = ddata.get('detail') if isinstance(ddata, dict) else ddata
                                        st.error(f"Falha ({dstatus}): {detail}")
                                    st.rerun()
                            if not gid:
                                st.caption("(ID ausente - registro inconsistente)")
                else:
                    st.error(f"Falha ao listar grupos ({groups_status}): {groups_data}")

        # ---- Tab Inscrições ----
        with tabs[1]:
            st.subheader("Nova Inscrição")
            colA, colB, colC = st.columns(3)
            with colA:
                e_name = st.text_input("Nome do candidato", key="e_name")
            with colB:
                e_age = st.number_input("Idade", min_value=0, max_value=120, value=30, key="e_age")
            with colC:
                e_cpf = st.text_input("CPF (somente números)", key="e_cpf")
            if st.button("Enviar Inscrição", type="primary"):
                if not e_name or (isinstance(e_name, str) and e_name.strip() == ""):
                    st.warning("Nome é obrigatório e não pode estar em branco.")
                else:
                    ok, data, status = await create_enrollment(client, e_name, int(e_age), e_cpf)
                    if ok:
                        st.success(f"Inscrição enviada. ID: {data.get('enrollment_id')}")
                        st.session_state['last_enrollment'] = data.get('enrollment_id')
                    else:
                        detail = data.get('detail') if isinstance(data, dict) else data
                        if status == 422:
                            st.error(f"Validação rejeitada: {detail}")
                        elif status == 400:
                            st.error(f"Dados inválidos: {detail}")
                        else:
                            st.error(f"Erro ({status}): {detail}")

        # ---- Tab Status ----
        with tabs[2]:
            st.subheader("Consultar Status de Inscrição")
            default_id: Optional[str] = st.session_state.get('last_enrollment')
            enr_id = st.text_input("Enrollment ID", value=default_id if default_id else "")
            if st.button("Consultar"):
                ok, data, status = await get_enrollment_status(client, enr_id)
                if ok:
                    st.json(data)
                else:
                    detail = data.get('detail') if isinstance(data, dict) else data
                    if status == 404:
                        st.warning(f"Não encontrada: {detail}")
                    elif status == 400:
                        st.error(f"ID inválido: {detail}")
                    else:
                        st.error(f"Erro ({status}): {detail}")

        # ---- Tab Sobre ----
        with tabs[3]:
            st.subheader("Sobre o Projeto")
            st.markdown(
                """
                **Age Groups & Enrollment** – Interface de apoio para a API.
                - CRUD de grupos etários
                - Solicitação e acompanhamento de inscrições
                - Demonstração de estados: queued, processing, completed, failed, rejected
                Código fonte em: [Repositório](https://github.com/gabriel-adutra/suthub-test)
                """
            )
            st.caption("Construído com Streamlit + httpx (async)")

asyncio.run(main_ui())
