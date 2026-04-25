import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import pytz
import json
import os
import re
from datetime import datetime, timedelta
import unicodedata

# =========================
# CONFIG
# ========================= 

WEBHOOK = "https://discord.com/api/webhooks/1496156584630419608/pgGWnevw4PvV_VryvMVoXTaML_Xep51evEdzFXg8inMYbX-ogI7hhs1BhcvYmekCG9l0"

URL_VIRTUE = "https://www.rucoyonline.com/guild/Guilt%20Of%20Virtue"
URL_PEACE = "https://www.rucoyonline.com/guild/Peace%20Killers"

BRASIL = pytz.timezone("America/Sao_Paulo")

ARQ_LOG = "pvp_log.json"
ARQ_STATS = "pvp_stats.json"

INTERVALO = 300  # 5 minutos

# =========================
# CACHE DE MEMBROS
# =========================

MEMBROS_VIRTUE = []
MEMBROS_PEACE = []
ULTIMOS_PVP_VIRTUE = []
FEED = []

def get_ts(e):
    if len(e) >= 3:
        return e[2] or 0
    return 0

def get_ordem(e):
    if len(e) >= 4:
        return e[3]
    return 0

# =========================
# DISCORD
# =========================

def enviar(msg):
    requests.post(WEBHOOK, json={"content": msg})

def enviar_e_pegar_id(msg):
    r = requests.post(WEBHOOK + "?wait=true", json={"content": msg})
    if r.status_code in (200, 201):
        return r.json()["id"]
    return None

def editar(msg_id, msg):
    requests.patch(WEBHOOK + f"/messages/{msg_id}", json={"content": msg})

# =========================
# JSON
# =========================

def carregar(file):
    if not os.path.exists(file):
        return {}
    return json.load(open(file))

def salvar(file, data):
    json.dump(data, open(file, "w"), indent=2)

# =========================
# PEGAR MEMBROS
# =========================

def pegar_membros(url):
    r = requests.get(url, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    membros = []

    for a in soup.select("a[href*='/characters/']"):
        nome = a.text.strip()
        membros.append(nome)

    return list(set(membros))

# =========================
# PEGAR PVP
# =========================

def pegar_pvp(nome):

    url = f"https://www.rucoyonline.com/characters/{nome.replace(' ', '%20')}"

    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        texto = soup.get_text(" ")

        if "Recent character kills and deaths" not in texto:
            return []

        parte = texto.split("Recent character kills and deaths")[1]
        tokens = parte.split()

        eventos = []
        atual = []

        for palavra in tokens:

            atual.append(palavra)

            if "ago" in palavra:

                frase = " ".join(atual)

                if "killed" not in frase:
                    atual = []
                    continue

                # =========================
                # 🔥 SPLIT SEGURO
                # =========================
                if "-" in frase:
                    parts = frase.split("-", 1)

                    if len(parts) < 2:
                        atual = []
                        continue

                    base = parts[0].strip()
                    tempo = parts[1].strip()

                else:
                    base = frase
                    tempo = ""

                # =========================
                # 🔥 FILTRO DE LIXO REAL
                # =========================
                if (
                    not base
                    or not tempo
                    or tempo.strip() == ""
                    or tempo.strip() == "[]"
                ):
                    atual = []
                    continue

                # =========================
                # 🔥 TIMESTAMP SAFE
                # =========================
                ts = tempo_para_datetime(tempo)

                if not ts:
                    continue

                eventos.append((base.strip(), tempo.strip(), ts))

                atual = []

        return eventos

    except Exception as e:
        print("Erro pegar PvP:", e)
        return []
    
def ultimos_pvp_virtue():

    eventos = [e for e in ULTIMOS_PVP_VIRTUE if isinstance(e[2], datetime)]

    # ordena por tempo real
    eventos = sorted(eventos, key=lambda x: x[2] or datetime.min, reverse=True)

    # ❌ NÃO remove duplicados por base
    return eventos

def montar_msg_virtue():

    agora_str = datetime.now(BRASIL).strftime("%H:%M")

    msg = "⚔️ **ULTIMOS PvPs (random)** ⚔️\n\n"

    filtrados = []

    for e in FEED:

        # 🔥 só aceita estrutura correta
        if len(e) != 4:
            continue

        base, tempo, ts, ordem = e

        if not base or "killed" not in base:
            continue

        killers, morto = normalizar_kill(base)

        if not killers or not morto:
            continue

        killers_lista = killers.split(" & ")
        killers_norm = [limpar_nome(k) for k in killers_lista]
        morto_norm = limpar_nome(morto)

        killer_virtue = any(k in MEMBROS_VIRTUE for k in killers_norm)
        morto_virtue = morto_norm in MEMBROS_VIRTUE

        # 🔥 Virtue vs QUALQUER UM
        if killer_virtue or morto_virtue:

            icon = "🟦" if killer_virtue else "🟥"

            filtrados.append((icon, base, tempo, ts, ordem))

    # =========================
    # 🔥 FILTRO REAL (últimas 2h)
    # =========================
    limite = datetime.now() - timedelta(hours=2)

    filtrados_corrigidos = []

    for e in filtrados:

        ts = e[3]

        if isinstance(ts, datetime):
            ts_dt = ts

        elif isinstance(ts, (int, float)):
            ts_dt = datetime.fromtimestamp(ts)

        else:
            continue

        if ts_dt >= limite:
            filtrados_corrigidos.append(e)

    filtrados = filtrados_corrigidos

    # =========================
    # 🔥 ORDENAÇÃO (mais recente primeiro)
    # =========================
    filtrados.sort(key=lambda x: x[3] if isinstance(x[3], datetime) else datetime.fromtimestamp(x[3]), reverse=True)

    # =========================
    # 🔥 OUTPUT
    # =========================
    if not filtrados:
        msg += "_Nenhum PvP recente._\n"
    else:
        for icon, base, tempo, ts, ordem in filtrados[:10]:

            killers, morto = normalizar_kill(base)

            if not killers or not morto:
                continue

            killers_lista = killers.split(" & ")
            killers_fmt = " and ".join([f"**{k.strip()}**" for k in killers_lista])
            morto_fmt = f"**{morto.strip()}**"

            msg += f"{icon} {killers_fmt} killed {morto_fmt} - _[{tempo}]_\n"

    msg += f"\n**⏱️ Atualizado:** _{agora_str}_"

    return msg[:1900]

def atualizar_membros():
    global MEMBROS_VIRTUE, MEMBROS_PEACE

    print("\n🔄 Atualizando membros das guilds...")

    try:
        v = pegar_membros(URL_VIRTUE)

        if v and len(v) > 5:  # 🔥 evita lista bugada/vazia
            MEMBROS_VIRTUE = [limpar_nome(m) for m in v]
            print(f"✅ Virtue atualizada ({len(MEMBROS_VIRTUE)})")
        else:
            print("⚠️ Virtue NÃO atualizada (resposta inválida)")

    except Exception as e:
        print("❌ Erro Virtue:", e)

    try:
        p = pegar_membros(URL_PEACE)

        if p and len(p) > 5:
            MEMBROS_PEACE = [limpar_nome(m) for m in p]
            print(f"✅ Peace atualizada ({len(MEMBROS_PEACE)})")
        else:
            print("⚠️ Peace NÃO atualizada (resposta inválida)")

    except Exception as e:
        print("❌ Erro Peace:", e)

    print(f"🟦 Virtue membros: {len(MEMBROS_VIRTUE)}")
    print(f"🟥 Peace membros: {len(MEMBROS_PEACE)}")
    
def analisar_pvp():

    global FEED

    print("\n🔎 INICIANDO ANALISE PVP...\n")

    membros_v = MEMBROS_VIRTUE
    membros_p = MEMBROS_PEACE

    print(f"🟦 Virtue membros: {len(membros_v)}")
    print(f"🟥 Peace membros: {len(membros_p)}\n")

    log = carregar(ARQ_LOG)
    stats = carregar(ARQ_STATS)

    if not stats:
        stats = {"virtue": {}, "peace": {}}

    novas_kills = []

    for nome in membros_v:

        eventos = pegar_pvp(nome)

        # 🔥 CORRETO: eventos tem 3 valores
        for base, tempo, ts in eventos:

            if not base or "killed" not in base:
                continue

            killers, morto = normalizar_kill(base)

            if not killers or not morto:
                continue

            killers_lista = re.split(r" & | , ", killers)
            killers_norm = [limpar_nome(k).strip() for k in killers_lista]
            morto_norm = limpar_nome(morto).strip()

            # 🔥 APPEND-ONLY (com timestamp real)
            FEED.append((base, tempo, ts or 0, time.time()))

            if len(FEED) > 500:
                FEED.pop(0)

            log_key = f"{' & '.join(sorted(killers_lista))} killed {morto} | {tempo}"

            # 🟦 VIRTUE matou PEACE
            if any(k in membros_v for k in killers_norm) and morto_norm in membros_p:

                print(f"🟦 {base} [{tempo}]")

                log[log_key] = True
                novas_kills.append(("VIRTUE", base, tempo, ts))

                for k in killers_lista:
                    k_norm = limpar_nome(k)
                    if k_norm in membros_v:
                        stats["virtue"][k_norm] = stats["virtue"].get(k_norm, 0) + 1

            # 🟥 PEACE matou VIRTUE
            elif any(k in membros_p for k in killers_norm) and morto_norm in membros_v:

                print(f"🟥 {base} [{tempo}]")

                log[log_key] = True
                novas_kills.append(("PEACE", base, tempo, ts))

                for k in killers_lista:
                    k_norm = limpar_nome(k)
                    if k_norm in membros_p:
                        stats["peace"][k_norm] = stats["peace"].get(k_norm, 0) + 1

        time.sleep(0.3)

    salvar(ARQ_LOG, log)
    salvar(ARQ_STATS, stats)

    print(f"\n✅ Novas kills detectadas: {len(novas_kills)}\n")

    return novas_kills, stats

def normalizar_kill(e):

    try:
        # remove tempo
        base = e.split(" - ")[0].strip()

        partes = base.split("killed", 1)

        if len(partes) != 2:
            return [], ""

        killers_txt, morto = partes

        # padroniza separadores
        killers_txt = killers_txt.replace(" and ", ",")
        killers_lista = [k.strip() for k in killers_txt.split(",") if k.strip()]

        # killers_lista = sorted(killers_lista)

        killers_norm = " & ".join(killers_lista)

        return killers_norm, morto.strip()

    except:
        return [], ""

def limpar_nome(nome):
    nome = unicodedata.normalize("NFKC", nome)
    nome = nome.replace("\u00a0", " ")  # NBSP
    nome = re.sub(r"\s+", " ", nome)    # espaços múltiplos
    return nome.strip().lower()

# =========================
# MONTAR MSG (PAINEL)
# =========================

def montar_msg():

    msg = "🗡️ **PVP TRACKER** 🗡️\n\n"
    msg += "**🟦 Virtue  ⚔️  Peace 🟥**\n\n"

    # 🔥 garante estrutura correta
    eventos = [e for e in FEED if len(e) >= 4]

    filtrados = []

    for e in eventos:

        base, tempo, ts, ordem = e

        if not base or "killed" not in base:
            continue

        killers, morto = normalizar_kill(base)

        if not killers or not morto:
            continue

        killers_lista = killers.split(" & ")
        killers_norm = [limpar_nome(k) for k in killers_lista]
        morto_norm = limpar_nome(morto)

        killer_virtue = any(k in MEMBROS_VIRTUE for k in killers_norm)
        killer_peace = any(k in MEMBROS_PEACE for k in killers_norm)

        morto_virtue = morto_norm in MEMBROS_VIRTUE
        morto_peace = morto_norm in MEMBROS_PEACE

        if (killer_virtue and morto_peace) or (killer_peace and morto_virtue):

            icon = "🟦" if killer_virtue else "🟥"

            filtrados.append((icon, base, tempo, ts, ordem))

    # =========================
    # 🔥 FILTRO DE TEMPO (últimas 2h)
    # =========================
    agora = datetime.now(BRASIL)
    limite = agora.timestamp() - (2 * 3600)

    filtrados_corrigidos = []

    for e in filtrados:

        ts = e[3]

        if isinstance(ts, datetime):
            ts_valor = ts.timestamp()
        elif isinstance(ts, (int, float)):
            ts_valor = ts
        else:
            continue

        if ts_valor >= limite:
            filtrados_corrigidos.append(e)

    filtrados = filtrados_corrigidos

    # =========================
    # 🔥 ORDENAÇÃO REAL (igual site)
    # =========================
    filtrados.sort(key=lambda x: x[4], reverse=True)

    # =========================
    # 🔥 MONTA MSG
    # =========================
    if not filtrados:
        msg += "_Nenhum PvP recente._\n"
        return msg

    for icon, base, tempo, ts, ordem in filtrados[:10]:

        killers, morto = normalizar_kill(base)

        if not killers or not morto:
            continue

        killers_lista = killers.split(" & ")

        killers_fmt = " and ".join([f"**{k.strip()}**" for k in killers_lista])
        morto_fmt = f"**{morto.strip()}**"

        msg += f"{icon} {killers_fmt} killed {morto_fmt} - _[{tempo}]_\n"

    return msg[:1900]
    
# =========================
# RESUMO DIÁRIO
# =========================

def top3(d):
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:3]

def resumo_diario(stats):

    agora_ts = time.time()
    limite = agora_ts - (24 * 60 * 60)  # 24 horas

    msg = "📊 **RESUMO PVP — VIRTUE vs PEACE** 📊\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    kills_v = {}
    kills_p = {}

    mortes_virtue = 0
    mortes_peace = 0

    # 🔥 FILTRA PELO TEMPO REAL
    for e in FEED:

        if len(e) == 4:
            base, tempo, ts, ordem = e
        else:
            base, tempo, ts = e
            ordem = 0

        # usa timestamp real
        if isinstance(ts, datetime):
            ts_check = ts.timestamp()
        else:
            ts_check = ts

        if ts_check < limite:
            continue

        killers, morto = normalizar_kill(base)

        if not killers or not morto:
            continue

        killers_lista = killers.split(" & ")
        killers_norm = [limpar_nome(k) for k in killers_lista]
        morto_norm = limpar_nome(morto)

        killer_virtue = any(k in MEMBROS_VIRTUE for k in killers_norm)
        killer_peace = any(k in MEMBROS_PEACE for k in killers_norm)

        morto_virtue = morto_norm in MEMBROS_VIRTUE
        morto_peace = morto_norm in MEMBROS_PEACE

        # =========================
        # 🟦 VIRTUE MATOU PEACE
        # =========================
        if killer_virtue and morto_peace:

            mortes_peace += 1

            for k in killers_lista:
                k_norm = limpar_nome(k)
                if k_norm in MEMBROS_VIRTUE:
                    kills_v[k_norm] = kills_v.get(k_norm, 0) + 1

        # =========================
        # 🟥 PEACE MATOU VIRTUE
        # =========================
        elif killer_peace and morto_virtue:

            mortes_virtue += 1

            for k in killers_lista:
                k_norm = limpar_nome(k)
                if k_norm in MEMBROS_PEACE:
                    kills_p[k_norm] = kills_p.get(k_norm, 0) + 1

    # =========================
    # TOP VIRTUE
    # =========================
    msg += "🟦 **Virtue**\n"

    top_v = sorted(kills_v.items(), key=lambda x: x[1], reverse=True)[:3]

    if top_v:
        medalhas = ["🥇","🥈","🥉"]
        for i, (nome, qtd) in enumerate(top_v):
            msg += f"{medalhas[i]} {nome} → {qtd} kills\n"
    else:
        msg += "_Nenhum_\n"

    # =========================
    # TOP PEACE
    # =========================
    msg += "\n🟥 **Peace**\n"

    top_p = sorted(kills_p.items(), key=lambda x: x[1], reverse=True)[:3]

    if top_p:
        medalhas = ["🥇","🥈","🥉"]
        for i, (nome, qtd) in enumerate(top_p):
            msg += f"{medalhas[i]} {nome} → {qtd} kills\n"
    else:
        msg += "_Nenhum_\n"

    # =========================
    # MORTES
    # =========================
    msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "💀 **Mortes totais (últimas 23h)**\n\n"
    msg += f"🟦 Virtue → {mortes_virtue} mortes\n"
    msg += f"🟥 Peace → {mortes_peace} mortes\n"

    # =========================
    # CASO SEM PVP
    # =========================
    if mortes_virtue == 0 and mortes_peace == 0:
        msg = "📊 **RESUMO PVP — VIRTUE vs PEACE** 📊\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "Nenhum PvP nas últimas 23h."

    enviar(msg)

# =========================
# HORÁRIO 03H
# =========================

def segundos_ate_3h():

    agora = datetime.now(BRASIL)

    alvo = agora.replace(hour=3, minute=0, second=0, microsecond=0)

    if agora >= alvo:
        alvo += timedelta(days=1)

    return (alvo - agora).total_seconds()

def tempo_para_segundos(tempo):

    tempo = tempo.lower().replace("about ", "").strip()

    partes = tempo.split()

    try:
        n = int(partes[0])
    except:
        return 999999999  # fallback

    if "minute" in tempo:
        return n * 60

    if "hour" in tempo:
        return n * 3600

    if "day" in tempo:
        return n * 86400

    return 999999999

def tempo_para_datetime(txt):

    now = datetime.now()

    txt = txt.lower()

    num = int(re.findall(r"\d+", txt)[0])

    if "minute" in txt:
        return now - timedelta(minutes=num)

    if "hour" in txt:
        return now - timedelta(hours=num)

    if "day" in txt:
        return now - timedelta(days=num)

    # fallback seguro
    return now

# =========================
# LOOP
# =========================

print("🔥 Bot PvP iniciado")

msg_id = None

# 🔥 CARREGA MEMBROS AO INICIAR
atualizar_membros()

# 🔁 controle de atualização
ultimo_update_membros = time.time()

proximo_resumo = time.time() + segundos_ate_3h()

while True:

    try:

        # 🔄 atualiza membros a cada 10 minutos
        if time.time() - ultimo_update_membros > 600:
            atualizar_membros()
            ultimo_update_membros = time.time()

        # =========================
        # WAR TRACK
        # =========================
        novas, stats = analisar_pvp()

        # =========================
        # MENSAGEM FINAL (usa cache global correto)
        # =========================
        msg = montar_msg() + "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n" + montar_msg_virtue()

        if msg_id:
            editar(msg_id, msg)
        else:
            # 🔥 cria painel inicial
            msg_id = enviar_e_pegar_id(msg)

        # =========================
        # LOG LIMPO (IMPORTANTE)
        # =========================
        print(f"🧠 Cache PvP Virtue: {len(ULTIMOS_PVP_VIRTUE)} eventos")
        print(f"⏱ Próxima atualização de membros em: {int(600 - (time.time() - ultimo_update_membros))}s")

        # =========================
        # RESUMO 03H
        # =========================
        if time.time() >= proximo_resumo:

            resumo_diario(stats)
            proximo_resumo = time.time() + 86400

        time.sleep(INTERVALO)

    except Exception as e:

        print("Erro:", e)
        time.sleep(60)
