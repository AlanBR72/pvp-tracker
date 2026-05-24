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

    banco = carregar(ARQ_PVP_DB)

    if not isinstance(banco, list):
        banco = []

    for nome in MEMBROS_VIRTUE:

        eventos = pegar_pvp(nome)

        if not isinstance(eventos, list):
            continue

        for i, evento in enumerate(eventos):

            # 🔥 proteção absoluta
            if (
                not evento
                or not isinstance(evento, (list, tuple))
                or len(evento) < 3
            ):
                continue

            try:
                base = evento[0]
                tempo = evento[1]
                ts = evento[2]
            except:
                continue

            if not base or "killed" not in base:
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

                ts_int = 0

                try:
                    ts_int = int(ts.timestamp())
                except:
                    pass

                FEED.append((
                    base,
                    tempo,
                    ts_int,
                    i
                ))

            FEED = FEED[-500:]

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

            icon = "🟦" if killer_virtue else "🟥"

            ja_existe = any(
                isinstance(p, dict)
                and p.get("base") == base
                and p.get("tempo") == tempo
                and p.get("ordem") == i
                for p in banco
            )

            if ja_existe:
                continue

            ts_int = 0

            try:
                ts_int = int(ts.timestamp())
            except:
                pass

            print(f"{icon} {base} [{tempo}]")

            banco.append({
                "icon": icon,
                "base": base,
                "tempo": tempo,
                "timestamp": ts_int,
                "ordem": i
            })

    banco.sort(
        key=lambda x: (
            -x.get("timestamp", 0),
            x.get("ordem", 999999)
        )
    )

    banco = banco[:300]

    salvar(ARQ_PVP_DB, banco)

    print(f"\n🧠 PvPs guild salvos: {len(banco)}")

    # =====================================
    # RETORNAR KILLS FORMATADAS
    # =====================================

    kills_site = []

    for p in banco:

        try:

            killers, victim = normalizar_kill(
                p["base"]
            )

            kills_site.append({
                "killers": killers.split(" & "),
                "victim": victim,
                "tempo": p["tempo"]
            })

        except:
            continue

    return kills_site

# =========================
# MONTAR MSG
# =========================

def tempo_relativo(ts):

    agora = int(datetime.now().timestamp())

    diff = agora - ts

    if diff < 60:
        return "less than a minute ago"

    minutos = diff // 60

    if minutos < 60:

        if minutos == 1:
            return "1 minute ago"

        return f"{minutos} minutes ago"

    horas = minutos // 60

    if horas < 24:

        if horas == 1:
            return "about 1 hour ago"

        return f"about {horas} hours ago"

    dias = horas // 24

    if dias == 1:
        return "1 day ago"

    return f"{dias} days ago"

def filtrar_pvp_tracker(kills_site):

    kills_filtradas = []

    for kill in kills_site:

        killers = kill["killers"]
        victim = kill["victim"]

        killers_lower = [
            k.lower()
            for k in killers
        ]

        victim_lower = victim.lower()

        # =========================
        # IDENTIFICAR LADOS
        # =========================

        killer_virtue = any(
            "virtue" in k or "culpa" in k
            for k in killers_lower
        )

        killer_peace = any(
            "peace" in k
            for k in killers_lower
        )

        victim_virtue = (
            "virtue" in victim_lower
            or "culpa" in victim_lower
        )

        victim_peace = (
            "peace" in victim_lower
        )

        # =========================
        # FILTRAR APENAS
        # VIRTUE vs PEACE
        # =========================

        if (
            killer_virtue and victim_peace
        ) or (
            killer_peace and victim_virtue
        ):

            kills_filtradas.append(kill)

    return kills_filtradas

def gerar_msg_pvp_tracker(kills_filtradas):

    msg = ""

    msg += "🗡️ **PVP TRACKER** 🗡️\n\n"
    msg += "**🟦 Virtue  ⚔️  Peace 🟥**\n\n"

    # NÃO usar sorted()
    # NÃO usar set()
    # NÃO usar dict()
    # manter ordem ORIGINAL do site

    for kill in kills_filtradas:

        killers = kill["killers"]
        victim = kill["victim"]
        tempo = kill["tempo"]

        killers_lower = [
            k.lower()
            for k in killers
        ]

        victim_lower = victim.lower()

        killer_virtue = any(
            "virtue" in k or "culpa" in k
            for k in killers_lower
        )

        killer_peace = any(
            "peace" in k
            for k in killers_lower
        )

        victim_virtue = (
            "virtue" in victim_lower
            or "culpa" in victim_lower
        )

        victim_peace = (
            "peace" in victim_lower
        )

        # =========================
        # COR DO LADO
        # =========================

        emoji = "🟦"

        if killer_peace and victim_virtue:
            emoji = "🟥"

        # =========================
        # FORMATAR KILLERS
        # =========================

        killers_txt = " and ".join(
            f"**{k}**"
            for k in killers
        )

        msg += (
            f"{emoji} "
            f"{killers_txt} killed "
            f"**{victim}** "
            f"- _[{tempo}]_\n"
        )

    return msg

def montar_msg_virtue():

    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = "⚔️ **ULTIMOS PvPs (random)** ⚔️\n\n"

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

        analisar_pvp()

        # =====================================
        # CARREGA BANCO ATUALIZADO
        # =====================================

        banco = carregar(ARQ_PVP_DB)

        if not isinstance(banco, list):
            banco = []

        # =====================================
        # CONVERTE PARA FORMATO NOVO
        # =====================================

        kills_site = []

        for p in banco:

            try:

                base = p["base"]
                tempo = p["tempo"]

                killers, victim = normalizar_kill(base)

                if not killers or not victim:
                    continue

                kills_site.append({
                    "killers": killers.split(" & "),
                    "victim": victim,
                    "tempo": tempo
                })

            except:
                continue

        # =====================================
        # FILTRA WAR
        # =====================================

        kills_filtradas = filtrar_pvp_tracker(
            kills_site
        )

        # =====================================
        # GERAR MSG
        # =====================================

        msg = (
            gerar_msg_pvp_tracker(kills_filtradas)
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
