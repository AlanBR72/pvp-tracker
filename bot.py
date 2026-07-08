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

# Mostrar somente PvPs das últimas 23 horas
LIMITE_PVP_HORAS = 23

# =========================
# CACHE
# =========================

MEMBROS_VIRTUE = []
MEMBROS_PEACE = []
FEED = []

# =========================
# DISCORD
# =========================

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
    # PEACE
    # =========================

    try:

        p = pegar_membros(URL_PEACE)

        if p and len(p) > 5:

            MEMBROS_PEACE = [
                limpar_nome(m)
                for m in p
            ]

            print(f"✅ Peace atualizada ({len(MEMBROS_PEACE)})")

        else:
            print("⚠️ Peace inválida")

    except Exception as e:

        print("❌ Erro Peace:", e)

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

    kills_war = []
    vistos_war = set()

    agora = datetime.now()
    limite = agora - timedelta(hours=LIMITE_PVP_HORAS)

    # Mantém a busca em apenas UMA guilda: Virtue
    for nome in MEMBROS_VIRTUE:

        eventos = pegar_pvp(nome)

        if not isinstance(eventos, list):
            continue

        for i, evento in enumerate(eventos):

            try:
                base = evento[0]
                tempo = evento[1]
                ts = evento[2]
            except:
                continue

            if not base or "killed" not in base:
                continue

            # Só mostra PvPs dentro das últimas 23 horas
            if ts < limite:
                continue

            killers, morto = normalizar_kill(base)

            if not killers or not morto:
                continue

            killers_lista = killers.split(" & ")

            killers_norm = [
                limpar_nome(k)
                for k in killers_lista
            ]

            morto_norm = limpar_nome(morto)

            ts_int = 0

            try:
                ts_int = int(ts.timestamp())
            except:
                pass

            # =====================================
            # FEED RANDOM
            # =====================================

            existe_feed = any(
                len(e) >= 2
                and e[0] == base
                and e[1] == tempo
                for e in FEED
            )

            if not existe_feed:

                FEED.append((
                    base,
                    tempo,
                    ts_int,
                    i
                ))

            # Mantém somente cache recente para não mostrar PvP velho
            FEED = [
                e for e in FEED
                if len(e) >= 3 and e[2] >= int(limite.timestamp())
            ][-500:]

            # =====================================
            # FILTRO WAR
            # =====================================

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

            is_war = (
                (killer_virtue and morto_peace)
                or
                (killer_peace and morto_virtue)
            )

            if not is_war:
                continue

            # Não remove kills iguais pelo mesmo killer/vítima/tempo,
            # porque o site pode listar 2 ou 3 kills iguais no mesmo horário textual
            # Exemplo: "Virtuelessz killed Peace Aquillees - about 12 hours ago" repetido 3x.
            # A chave inclui o perfil lido e a ordem da linha para manter essas repetições.
            chave = (
                limpar_nome(nome),
                limpar_nome(base),
                tempo,
                i
            )

            if chave in vistos_war:
                continue

            vistos_war.add(chave)

            icon = "🟦" if killer_virtue else "🟥"

            kills_war.append({
                "icon": icon,
                "killers": killers_lista,
                "victim": morto,
                "tempo": tempo,
                "timestamp": ts_int,
                "ordem": i
            })

    # =====================================
    # ORDENAR MAIS RECENTES
    # =====================================

    kills_war.sort(
        key=lambda x: (
            -x["timestamp"],
            x["ordem"]
        )
    )

    print(f"\n🧠 PvPs WAR encontrados nas últimas {LIMITE_PVP_HORAS}h: {len(kills_war)}")

    return kills_war

# =========================
# MONTAR MSG
# =========================

def gerar_msg_pvp_tracker(kills_filtradas):

    msg = ""

    msg += "🗡️ **PVP TRACKER** 🗡️\n"
    msg += f"_Últimas {LIMITE_PVP_HORAS} horas_\n\n"
    msg += "**🟦 Virtue  ⚔️  Peace 🟥**\n\n"

    # =====================================
    # PEGAR 10 MAIS RECENTES
    # =====================================

    kills_exibir = kills_filtradas[:10]

    if not kills_exibir:

        msg += "_Nenhum PvP encontrado._\n"

    else:

        for kill in kills_exibir:

            killers = kill["killers"]
            victim = kill["victim"]
            tempo = kill["tempo"]
            icon = kill["icon"]

            killers_txt = " and ".join([
                f"**{k}**"
                for k in killers
            ])

            msg += (
                f"{icon} "
                f"{killers_txt} killed "
                f"**{victim}** "
                f"- _[{tempo}]_\n"
            )

    return msg

def montar_msg_virtue():

    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = f"⚔️ **ULTIMOS PvPs (random)** ⚔️\n_Últimas {LIMITE_PVP_HORAS} horas_\n\n"

    filtrados = FEED.copy()

    # 🔥 SORT IGUAL AO SITE
    filtrados.sort(
        key=lambda x: (
            -x[2],  # timestamp
            x[3]    # ordem no site
        )
    )

    if not filtrados:

        msg += "_Nenhum PvP encontrado._\n"

    else:

        for base, tempo, ts, ordem in filtrados[:10]:

            killers, morto = normalizar_kill(base)

            killers_lista = killers.split(" & ")

            killers_fmt = " and ".join([
                f"**{k.strip()}**"
                for k in killers_lista
            ])

            morto_fmt = f"**{morto.strip()}**"

            # 🔥 ICON RANDOM
            killers_norm = [
                limpar_nome(k)
                for k in killers_lista
            ]

            morto_norm = limpar_nome(morto)

            killer_virtue = any(
                k in MEMBROS_VIRTUE
                for k in killers_norm
            )

            icon = "🟦" if killer_virtue else "🟥"

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

        # =====================================
        # ANALISA PvPs
        # =====================================

        kills_site = analisar_pvp()

        # =====================================
        # GERAR MSG
        # =====================================

        msg = (
            gerar_msg_pvp_tracker(kills_site)
            + "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + montar_msg_virtue()
        )

        # =====================================
        # EDITAR MSG
        # =====================================

        if msg_id:

            editar(msg_id, msg)

        else:

            msg_id = enviar_e_pegar_id(msg)

        print(f"\n🧠 Cache PvP: {len(FEED)} eventos\n")

        time.sleep(INTERVALO)

    except Exception as e:

        print("Erro:", e)

        time.sleep(60)
