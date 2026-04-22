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

def pegar_pvp_virtue():

    membros = pegar_membros(URL_VIRTUE)

    eventos = []

    for nome in membros:

        pvp = pegar_pvp(nome)

        for e in pvp:

            if "killed" not in e:
                continue

            try:
                base = e.split(" - ")[0].strip()
                tempo = e.split(" - ")[1].strip()
            except:
                continue

            eventos.append((base, tempo))

    return eventos

def ultimos_pvp_virtue():

    eventos = pegar_pvp_virtue()

    vistos = set()
    unicos = []

    for base, tempo in eventos:

        chave = base

        if chave in vistos:
            continue

        vistos.add(chave)
        unicos.append((base, tempo))

    # pega só os 5 mais recentes
    return unicos[:5]

def gerar_msg_pvp_virtue():

    lista = ultimos_pvp_virtue()

    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = "⚔️ **ÚLTIMOS PVPs — VIRTUE** ⚔️\n\n"

    if not lista:
        msg += "_Nenhum PvP recente._"
        return msg

    for base, tempo in lista:

        # identifica se Virtue matou ou morreu
        if "Virtue" in base.split("killed")[0]:
            emoji = "🟦"  # matou
        else:
            emoji = "☠️"  # morreu

        msg += f"{emoji} {base} [{tempo}]\n"

    msg += f"\n_⏱️ Atualizado: {agora}_"

    return msg[:1900]

def montar_bloco_pvp_virtue():

    lista = ultimos_pvp_virtue()

    msg = "🟦 **Últimos PvPs — Virtue**\n\n"

    if not lista:
        msg += "_Nenhum PvP recente._"
        return msg

    for base, tempo in lista:

        if "Virtue" in base.split("killed")[0]:
            emoji = "🟦"
        else:
            emoji = "☠️"

        msg += f"{emoji} {base} [{tempo}]\n"

    return msg

# =========================
# ANALISAR PVP
# =========================

def analisar_pvp():

    membros_v = pegar_membros(URL_VIRTUE)
    membros_p = pegar_membros(URL_PEACE)

    log = carregar(ARQ_LOG)
    stats = carregar(ARQ_STATS)

    if not stats:
        stats = {"virtue": {}, "peace": {}}

    novas_kills = []

    for nome in membros_v + membros_p:

        eventos = pegar_pvp(nome)

        for e in eventos:

            if "killed" not in e:
                continue

            killers, morto = normalizar_kill(e)

            if not killers or not morto:
                continue

            # cria chave única
            chave = f"{' & '.join(killers)} killed {morto}"

            if chave in log:
                continue

            # =========================
            # VIRTUE MATOU PEACE
            # =========================
            if any(k in membros_v for k in killers) and morto in membros_p:

                log[chave] = True
                novas_kills.append(("VIRTUE", chave))

                for k in killers:
                    if k in membros_v:
                        stats["virtue"][k] = stats["virtue"].get(k, 0) + 1

            # =========================
            # PEACE MATOU VIRTUE
            # =========================
            elif any(k in membros_p for k in killers) and morto in membros_v:

                log[chave] = True
                novas_kills.append(("PEACE", chave))

                for k in killers:
                    if k in membros_p:
                        stats["peace"][k] = stats["peace"].get(k, 0) + 1

    salvar(ARQ_LOG, log)
    salvar(ARQ_STATS, stats)

    return novas_kills, stats

def normalizar_kill(e):

    try:
        # remove tempo
        base = e.split(" - ")[0].strip()

        killers_txt, morto = base.split("killed")

        # padroniza separadores
        killers_txt = killers_txt.replace(" and ", ",")
        killers_lista = [k.strip() for k in killers_txt.split(",") if k.strip()]

        killers_lista = sorted(killers_lista)

        killers_norm = " & ".join(killers_lista)

        return killers_norm, morto.strip()

    except:
        return [], ""

# =========================
# MONTAR MSG (PAINEL)
# =========================

def montar_msg(kills_cache):

    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = "⚔️ **PVP TRACKER — VIRTUE vs PEACE** ⚔️\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "**🟦 Virtue  ⚔️  Peace 🟥**\n\n"

    # =========================
    # GUERRA
    # =========================
    if not kills_cache:
        msg += "_Nenhuma kill registrada ainda._\n"
    else:
        for tipo, texto in kills_cache[-20:]:

            emoji = "🟦" if tipo == "VIRTUE" else "🟥"
            hora = datetime.now(BRASIL).strftime("%H:%M")

            msg += f"{emoji} {texto} [{hora}]\n"

    # =========================
    # NOVO BLOCO (VIRTUE GLOBAL)
    # =========================
    msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += montar_bloco_pvp_virtue()

    msg += f"\n\n_⏱️ Última atualização: {agora}_"

    return msg[:1900]
    
# =========================
# RESUMO DIÁRIO
# =========================

def top3(d):
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:3]

def resumo_diario(stats):

    msg = "📊 **RESUMO PVP — VIRTUE vs PEACE** 📊\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # =========================
    # TOP VIRTUE
    # =========================
    msg += "🟦 **Virtue**\n"

    top_v = top3(stats.get("virtue", {}))

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

    top_p = top3(stats.get("peace", {}))

    if top_p:
        medalhas = ["🥇","🥈","🥉"]
        for i, (nome, qtd) in enumerate(top_p):
            msg += f"{medalhas[i]} {nome} → {qtd} kills\n"
    else:
        msg += "_Nenhum_\n"

    # =========================
    # MORTES
    # =========================
    mortes_virtue = sum(stats.get("peace", {}).values())
    mortes_peace = sum(stats.get("virtue", {}).values())

    msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "💀 **Mortes totais**\n\n"
    msg += f"🟦 Virtue → {mortes_virtue} mortes\n"
    msg += f"🟥 Peace → {mortes_peace} mortes\n"

    # =========================
    # CASO SEM PVP
    # =========================
    if mortes_virtue == 0 and mortes_peace == 0:
        msg = "📊 **RESUMO PVP — VIRTUE vs PEACE** 📊\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "Nenhum PvP registrado hoje."

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

        # =========================
        # WAR TRACK
        # =========================
        novas, stats = analisar_pvp()

        if novas:
            kills_cache.extend(novas)

        # =========================
        # MENSAGEM FINAL (COM NOVO BLOCO)
        # =========================
        msg = montar_msg(kills_cache)

        if msg_id:
            editar(msg_id, msg)
        else:
            msg_id = enviar_e_pegar_id(msg)

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
