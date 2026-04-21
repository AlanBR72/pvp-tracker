import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import pytz
import json
import os

# =========================
# CONFIG
# =========================

WEBHOOK = "https://discord.com/api/webhooks/1496156584630419608/pgGWnevw4PvV_VryvMVoXTaML_Xep51evEdzFXg8inMYbX-ogI7hhs1BhcvYmekCG9l0"

URL_VIRTUE = "https://www.rucoyonline.com/guild/Guilt%20Of%20Virtue"
URL_PEACE = "https://www.rucoyonline.com/guild/Peace%20Killers"

BRASIL = pytz.timezone("America/Sao_Paulo")

ARQ_LOG = "pvp_log.json"
ARQ_STATS = "pvp_stats.json"

INTERVALO = 60  # 1 minuto

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

        texto = soup.text

        if "killed" not in texto:
            return []

        eventos = []

        for linha in texto.split("\n"):
            if "killed" in linha:
                eventos.append(linha.strip())

        return eventos

    except:
        return []

# =========================
# ANALISAR PVP
# =========================

def analisar_pvp():

    membros_v = pegar_membros(URL_VIRTUE)
    membros_p = pegar_membros(URL_PEACE)

    log = carregar(ARQ_LOG)
    stats = carregar(ARQ_STATS)

    if not stats:
        stats = {
            "virtue": {},
            "peace": {}
        }

    novas_kills = []

    for nome in membros_v + membros_p:

        eventos = pegar_pvp(nome)

        for e in eventos:

            if e in log:
                continue

            if "killed" not in e:
                continue

            try:
                killer = e.split("killed")[0].strip()
                morto = e.split("killed")[1].split("[")[0].strip()
            except:
                continue

            if killer in membros_v and morto in membros_p:

                log[e] = True
                novas_kills.append(("VIRTUE", e))
                stats["virtue"][killer] = stats["virtue"].get(killer, 0) + 1

            elif killer in membros_p and morto in membros_v:

                log[e] = True
                novas_kills.append(("PEACE", e))
                stats["peace"][killer] = stats["peace"].get(killer, 0) + 1

    salvar(ARQ_LOG, log)
    salvar(ARQ_STATS, stats)

    return novas_kills, stats

# =========================
# MONTAR MSG (PAINEL)
# =========================

def montar_msg(kills_cache):

    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = f"⚔️ **WAR TRACKER — VIRTUE vs PEACE** ⚔️\n"
    msg += f"_Atualizado: {agora}_\n\n"

    if not kills_cache:
        msg += "_Nenhuma kill recente_"
        return msg

    linhas = []

    for tipo, texto in kills_cache[-20:]:

        emoji = "🟦" if tipo == "VIRTUE" else "🟥"
        linhas.append(f"{emoji} {texto}")

    msg += "\n".join(linhas)

    return msg[:1900]

# =========================
# RESUMO DIÁRIO
# =========================

def top3(d):
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:3]

def resumo_diario(stats):

    msg = "📊 **RESUMO PVP — VIRTUE vs PEACE** 📊\n\n"

    # RANK VIRTUE
    msg += "🟦 **Top killers Virtue**\n"
    top_v = top3(stats.get("virtue", {}))

    if top_v:
        for nome, qtd in top_v:
            msg += f"• {nome} → {qtd} kills\n"
    else:
        msg += "_Nenhum_\n"

    # RANK PEACE
    msg += "\n🟥 **Top killers Peace**\n"
    top_p = top3(stats.get("peace", {}))

    if top_p:
        for nome, qtd in top_p:
            msg += f"• {nome} → {qtd} kills\n"
    else:
        msg += "_Nenhum_\n"

    # MORTES
    mortes_virtue = sum(stats.get("peace", {}).values())
    mortes_peace = sum(stats.get("virtue", {}).values())

    msg += "\n\n☠️ **Mortes na guerra**\n"
    msg += f"🟦 Virtue morreu → {mortes_virtue}\n"
    msg += f"🟥 Peace morreu → {mortes_peace}\n"

    enviar(msg)

    # reset diário
    salvar(ARQ_STATS, {
        "virtue": {},
        "peace": {}
    })

# =========================
# HORÁRIO 03H
# =========================

def segundos_ate_3h():

    agora = datetime.now(BRASIL)

    alvo = agora.replace(hour=3, minute=0, second=0, microsecond=0)

    if agora >= alvo:
        alvo += timedelta(days=1)

    return (alvo - agora).total_seconds()

# =========================
# LOOP
# =========================

print("🔥 Bot PvP iniciado")

msg_id = None
kills_cache = []

proximo_resumo = time.time() + segundos_ate_3h()

while True:

    try:

        novas, stats = analisar_pvp()

        if novas:
            kills_cache.extend(novas)

        msg = montar_msg(kills_cache)

        if msg_id:
            editar(msg_id, msg)
        else:
            msg_id = enviar_e_pegar_id(msg)

        # RESUMO 03H
        if time.time() >= proximo_resumo:

            resumo_diario(stats)

            proximo_resumo = time.time() + 86400

        time.sleep(INTERVALO)

    except Exception as e:

        print("Erro:", e)
        time.sleep(60)
