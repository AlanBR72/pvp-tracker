import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import pytz
import re
import unicodedata
import os
import json

# =========================
# CONFIG
# =========================

WEBHOOK = "https://discord.com/api/webhooks/1496156584630419608/pgGWnevw4PvV_VryvMVoXTaML_Xep51evEdzFXg8inMYbX-ogI7hhs1BhcvYmekCG9l0"

URL_VIRTUE = "https://www.rucoyonline.com/guild/Guilt%20Of%20Virtue"

URL_PEACE = "https://www.rucoyonline.com/guild/Peace%20Killers"

BRASIL = pytz.timezone("America/Sao_Paulo")

INTERVALO = 300  # 5 minutos

# =========================
# CACHE
# =========================

MEMBROS_VIRTUE = []
MEMBROS_PEACE = []
ARQ_PVP_DB = "pvp_db.json"
FEED = []

# =========================
# DISCORD
# =========================

def carregar(file):

    if not os.path.exists(file):
        return []

    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)

    except:
        return []

def salvar(file, data):

    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def enviar_e_pegar_id(msg):
    r = requests.post(WEBHOOK + "?wait=true", json={"content": msg})

    if r.status_code in (200, 201):
        return r.json()["id"]

    return None

def editar(msg_id, msg):
    requests.patch(
        WEBHOOK + f"/messages/{msg_id}",
        json={"content": msg}
    )

# =========================
# UTILS
# =========================

def limpar_nome(nome):

    nome = unicodedata.normalize("NFKC", nome)
    nome = nome.replace("\u00a0", " ")
    nome = re.sub(r"\s+", " ", nome)

    return nome.strip().lower()

def tempo_para_datetime(txt):

    now = datetime.now()

    txt = txt.lower()

    nums = re.findall(r"\d+", txt)

    if not nums:
        return now

    num = int(nums[0])

    if "minute" in txt:
        return now - timedelta(minutes=num)

    if "hour" in txt:
        return now - timedelta(hours=num)

    if "day" in txt:
        return now - timedelta(days=num)

    return now

def normalizar_kill(e):

    try:

        base = e.split(" - ")[0].strip()

        partes = base.split("killed", 1)

        if len(partes) != 2:
            return "", ""

        killers_txt, morto = partes

        killers_txt = killers_txt.replace(" and ", ",")

        killers_lista = [
            k.strip()
            for k in killers_txt.split(",")
            if k.strip()
        ]

        killers_norm = " & ".join(killers_lista)

        return killers_norm, morto.strip()

    except:
        return "", ""

# =========================
# PEGAR MEMBROS
# =========================

def pegar_membros(url):

    r = requests.get(url, timeout=15)

    soup = BeautifulSoup(r.text, "html.parser")

    membros = []

    for a in soup.select("a[href*='/characters/']"):

        nome = a.text.strip()

        if nome:
            membros.append(nome)

    return list(set(membros))

def atualizar_membros():

    global MEMBROS_VIRTUE
    global MEMBROS_PEACE

    print("\n🔄 Atualizando membros...\n")

    # =========================
    # VIRTUE
    # =========================

    try:

        v = pegar_membros(URL_VIRTUE)

        if v and len(v) > 5:

            MEMBROS_VIRTUE = [
                limpar_nome(m)
                for m in v
            ]

            print(f"✅ Virtue atualizada ({len(MEMBROS_VIRTUE)})")

        else:
            print("⚠️ Virtue inválida")

    except Exception as e:

        print("❌ Erro Virtue:", e)

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

                if "-" not in frase:
                    atual = []
                    continue

                parts = frase.split("-", 1)

                if len(parts) < 2:
                    atual = []
                    continue

                base = parts[0].strip()
                tempo = parts[1].strip()

                if not base or not tempo:
                    atual = []
                    continue

                ts = tempo_para_datetime(tempo)

                eventos.append((base, tempo, ts))

                atual = []

        return eventos

    except Exception as e:

        print("Erro pegar PvP:", e)

        return []

# =========================
# ANALISAR PVP
# =========================

def analisar_pvp():

    global FEED

    print("\n🔎 INICIANDO ANALISE PVP...\n")

    print(f"🟦 Virtue membros: {len(MEMBROS_VIRTUE)}")
    print(f"🟥 Peace membros: {len(MEMBROS_PEACE)}\n")

    banco = carregar(ARQ_PVP_DB)

    for nome in MEMBROS_VIRTUE:

        eventos = pegar_pvp(nome)

        for i, (base, tempo, ts) in enumerate(eventos):

            if not base or "killed" not in base:
                continue

            killers, morto = normalizar_kill(base)

            if not killers or not morto:
                continue

            killers_lista = re.split(r" & | , ", killers)

            killers_norm = [
                limpar_nome(k).strip()
                for k in killers_lista
            ]

            morto_norm = limpar_nome(morto).strip()

            killer_virtue = any(
                k in MEMBROS_VIRTUE
                for k in killers_norm
            )

            killer_peace = any(
                k in MEMBROS_PEACE
                for k in killers_norm
            )

            morto_virtue = morto_norm in MEMBROS_VIRTUE
            morto_peace = morto_norm in MEMBROS_PEACE

            # =========================
            # RANDOM PVP (FEED)
            # =========================

            if killer_virtue or morto_virtue:

                icon = "🟦" if killer_virtue else "🟥"

                ordem = i

                if not any(
                    e[1] == base and e[2] == tempo
                    for e in FEED
                ):

                    FEED.append((
                        icon,
                        base,
                        tempo,
                        ts,
                        ordem
                    ))

                if len(FEED) > 500:
                    FEED.pop(0)

            # =========================
            # VIRTUE vs PEACE
            # =========================

            war_pvp = (
                (killer_virtue and morto_peace)
                or
                (killer_peace and morto_virtue)
            )

            if war_pvp:

                icon = "🟦" if killer_virtue else "🟥"

                registro = {
                    "icon": icon,
                    "base": base,
                    "tempo": tempo,
                    "timestamp": ts.timestamp(),
                    "horario": datetime.now(BRASIL).strftime("%d/%m/%Y %H:%M:%S")
                }

                existe = any(
                    x["base"] == base
                    and x["tempo"] == tempo
                    for x in banco
                )

                if not existe:

                    banco.append(registro)

                    print(f"{icon} {base} [{tempo}]")

        time.sleep(0.3)

    salvar(ARQ_PVP_DB, banco)

# =========================
# MONTAR MSG
# =========================

# =========================
# PAINEL WAR
# =========================

def montar_msg_war():

    banco = carregar(ARQ_PVP_DB)

    msg = "🗡️ **PVP TRACKER** 🗡️\n\n"
    msg += "**🟦 Virtue  ⚔️  Peace 🟥**\n\n"

    if not banco:

        msg += "_Nenhum PvP recente entre guilds._\n"

        return msg

    # 🔥 MAIS RECENTES PRIMEIRO
    banco.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    for pvp in banco[:10]:

        icon = pvp["icon"]

        killers, morto = normalizar_kill(pvp["base"])

        killers_lista = killers.split(" & ")

        killers_fmt = " and ".join([
            f"**{k.strip()}**"
            for k in killers_lista
        ])

        morto_fmt = f"**{morto.strip()}**"

        tempo = pvp["tempo"]

        msg += (
            f"{icon} "
            f"{killers_fmt} killed "
            f"{morto_fmt} "
            f"- _[{tempo}]_\n"
        )

    return msg[:1900]

def montar_msg_virtue():

    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = "⚔️ **ULTIMOS PvPs (random)** ⚔️\n\n"

    filtrados = FEED.copy()

    # 🔥 SORT IGUAL AO SITE
    filtrados.sort(
        key=lambda x: (
            -(x[3].timestamp() if isinstance(x[3], datetime) else 0),
            x[4]
        )
    )

    if not filtrados:

        msg += "_Nenhum PvP encontrado._\n"

    else:

        for icon, base, tempo, ts, ordem in filtrados[:10]:

            killers, morto = normalizar_kill(base)

            killers_lista = killers.split(" & ")

            killers_fmt = " and ".join([
                f"**{k.strip()}**"
                for k in killers_lista
            ])

            morto_fmt = f"**{morto.strip()}**"

            msg += (
                f"{icon} "
                f"{killers_fmt} killed "
                f"{morto_fmt} "
                f"- _[{tempo}]_\n"
            )

    msg += f"\n**⏱️ Atualizado:** _{agora}_"

    return msg[:1900]

# =========================
# LOOP
# =========================

print("🔥 Bot PvP iniciado")

msg_id = None

atualizar_membros()

ultimo_update_membros = time.time()

while True:

    try:

        # 🔄 atualiza membros a cada 10min
        if time.time() - ultimo_update_membros > 600:

            atualizar_membros()

            ultimo_update_membros = time.time()

        analisar_pvp()

        msg = (
            montar_msg_war()
            + "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + montar_msg_virtue()
        )

        if msg_id:

            editar(msg_id, msg)

        else:

            msg_id = enviar_e_pegar_id(msg)

        print(f"\n🧠 Cache PvP: {len(FEED)} eventos\n")

        time.sleep(INTERVALO)

    except Exception as e:

        print("Erro:", e)

        time.sleep(60)
