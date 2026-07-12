import json
import os
import random
import re
import time
import unicodedata
from datetime import datetime
from urllib.parse import quote

import pytz
import requests
from bs4 import BeautifulSoup

# =========================
# CONFIG
# =========================

WEBHOOK = "https://discord.com/api/webhooks/1496156584630419608/pgGWnevw4PvV_VryvMVoXTaML_Xep51evEdzFXg8inMYbX-ogI7hhs1BhcvYmekCG9l0"

URL_VIRTUE = "https://www.rucoyonline.com/guild/Guilt%20Of%20Virtue"
URL_PEACE = "https://www.rucoyonline.com/guild/Peace%20Killers"
URL_INFERNAL = "https://www.rucoyonline.com/guild/Infernal%20Cruelty"

BRASIL = pytz.timezone("America/Sao_Paulo")
INTERVALO = 600  # 5 minutos
LIMITE_PVP_HORAS = 23
MAX_EVENTOS_PAINEL = 10

# Proteção contra bloqueio 429 do site.
ATRASO_ENTRE_PERFIS = 2  # segundos entre páginas de personagens
MAX_TENTATIVAS_429 = 3
ESPERA_PADRAO_429 = 60

# Salva os IDs para continuar editando as mesmas mensagens após reiniciar o bot.
ARQUIVO_IDS = "painel_ids.json"

# =========================
# CACHE DE MEMBROS
# =========================

MEMBROS_VIRTUE = []
MEMBROS_PEACE = []
MEMBROS_INFERNAL = []

# Reutiliza a mesma conexão HTTP e envia um User-Agent comum.
SESSAO = requests.Session()
SESSAO.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
})

# =========================
# DISCORD
# =========================


def enviar_e_pegar_id(msg):
    try:
        resposta = requests.post(
            WEBHOOK + "?wait=true",
            json={"content": msg[:2000]},
            timeout=20,
        )

        if resposta.status_code in (200, 201):
            return resposta.json().get("id")

        print("❌ Erro ao enviar mensagem:", resposta.status_code, resposta.text)
    except Exception as erro:
        print("❌ Erro ao enviar mensagem:", erro)

    return None


def editar(msg_id, msg):
    try:
        resposta = requests.patch(
            WEBHOOK + f"/messages/{msg_id}",
            json={"content": msg[:2000]},
            timeout=20,
        )

        if resposta.status_code in (200, 204):
            return True

        print("⚠️ Não foi possível editar:", resposta.status_code, resposta.text)
    except Exception as erro:
        print("❌ Erro ao editar mensagem:", erro)

    return False


def carregar_ids():
    if not os.path.exists(ARQUIVO_IDS):
        return {"peace": None, "infernal": None, "random": None}

    try:
        with open(ARQUIVO_IDS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        return {
            "peace": dados.get("peace"),
            "infernal": dados.get("infernal"),
            "random": dados.get("random"),
        }
    except Exception as erro:
        print("⚠️ Erro ao carregar IDs:", erro)
        return {"peace": None, "infernal": None, "random": None}


def salvar_ids(ids):
    try:
        with open(ARQUIVO_IDS, "w", encoding="utf-8") as arquivo:
            json.dump(ids, arquivo, ensure_ascii=False, indent=2)
    except Exception as erro:
        print("⚠️ Erro ao salvar IDs:", erro)


def atualizar_painel(ids, chave, mensagem):
    msg_id = ids.get(chave)

    if msg_id and editar(msg_id, mensagem):
        return

    novo_id = enviar_e_pegar_id(mensagem)

    if novo_id:
        ids[chave] = novo_id
        salvar_ids(ids)

# =========================
# UTILS
# =========================


def limpar_nome(nome):
    nome = unicodedata.normalize("NFKC", nome)
    nome = nome.replace("\u00a0", " ")
    nome = re.sub(r"\s+", " ", nome)
    return nome.strip().lower()


def tempo_para_segundos(txt):
    """Converte o texto do site em idade, em segundos."""
    texto = txt.lower().strip()
    numeros = re.findall(r"\d+", texto)

    # Textos sem número, como "a few seconds ago", ficam no topo.
    if not numeros:
        if "second" in texto:
            return 0
        return 10**12

    numero = int(numeros[0])

    if "second" in texto:
        return numero
    if "minute" in texto:
        return numero * 60
    if "hour" in texto:
        return numero * 60 * 60
    if "day" in texto:
        return numero * 24 * 60 * 60
    if "week" in texto:
        return numero * 7 * 24 * 60 * 60

    return 10**12


def dentro_do_limite(tempo):
    return tempo_para_segundos(tempo) <= LIMITE_PVP_HORAS * 60 * 60


def normalizar_kill(base):
    try:
        partes = base.split("killed", 1)

        if len(partes) != 2:
            return [], ""

        killers_txt, morto = partes
        killers_txt = killers_txt.replace(" and ", ",")

        killers = [
            killer.strip()
            for killer in killers_txt.split(",")
            if killer.strip()
        ]

        return killers, morto.strip()
    except Exception:
        return [], ""


def traduzir_tempo(txt):
    texto = txt.lower().strip()
    numeros = re.findall(r"\d+", texto)

    if not numeros:
        if "second" in texto:
            return "há poucos segundos"
        return txt

    numero = int(numeros[0])

    if "second" in texto:
        return f"há {numero} s"
    if "minute" in texto:
        return f"há {numero} min"
    if "hour" in texto:
        return f"há {numero} h"
    if "day" in texto:
        return "há 1 dia" if numero == 1 else f"há {numero} dias"

    return txt


def formatar_killers(killers):
    return " + ".join(f"**{killer}**" for killer in killers)


def verbo_matar(quantidade):
    return "matou" if quantidade == 1 else "mataram"

# =========================
# MEMBROS
# =========================


def pegar_membros(url):
    resposta = SESSAO.get(url, timeout=20)
    resposta.raise_for_status()
    soup = BeautifulSoup(resposta.text, "html.parser")

    membros = []

    for link in soup.select("a[href*='/characters/']"):
        nome = link.get_text(strip=True)
        if nome:
            membros.append(nome)

    # Preserva a ordem e remove repetidos.
    return list(dict.fromkeys(membros))


def atualizar_membros():
    global MEMBROS_VIRTUE, MEMBROS_PEACE, MEMBROS_INFERNAL

    print("\n🔄 Atualizando listas de membros...\n")

    configuracoes = [
        ("Virtue", URL_VIRTUE, "virtue"),
        ("Peace Killers", URL_PEACE, "peace"),
        ("Infernal Cruelty", URL_INFERNAL, "infernal"),
    ]

    for nome_guilda, url, chave in configuracoes:
        try:
            membros = pegar_membros(url)

            if not membros:
                print(f"⚠️ Lista vazia: {nome_guilda}")
                continue

            normalizados = [limpar_nome(membro) for membro in membros]

            if chave == "virtue":
                MEMBROS_VIRTUE = normalizados
            elif chave == "peace":
                MEMBROS_PEACE = normalizados
            else:
                MEMBROS_INFERNAL = normalizados

            print(f"✅ {nome_guilda}: {len(normalizados)} membros")
        except Exception as erro:
            print(f"❌ Erro ao atualizar {nome_guilda}:", erro)

# =========================
# PVP
# =========================


def pegar_pvp(nome):
    url = "https://www.rucoyonline.com/characters/" + quote(nome)

    for tentativa in range(1, MAX_TENTATIVAS_429 + 1):
        try:
            resposta = SESSAO.get(url, timeout=20)

            if resposta.status_code == 429:
                retry_after = resposta.headers.get("Retry-After", "")

                try:
                    espera = max(int(retry_after), ESPERA_PADRAO_429)
                except (TypeError, ValueError):
                    espera = ESPERA_PADRAO_429 * tentativa

                # Pequena variação evita que todas as novas tentativas ocorram
                # exatamente no mesmo instante.
                espera += random.uniform(1, 5)

                print(
                    f"⏳ Limite 429 em {nome}. "
                    f"Aguardando {espera:.0f}s antes da tentativa "
                    f"{tentativa + 1}/{MAX_TENTATIVAS_429}..."
                )

                if tentativa < MAX_TENTATIVAS_429:
                    time.sleep(espera)
                    continue

                print(f"⚠️ PvP de {nome} ignorado neste ciclo após 429.")
                return []

            resposta.raise_for_status()
            soup = BeautifulSoup(resposta.text, "html.parser")
            texto = soup.get_text(" ")

            marcador = "Recent character kills and deaths"
            if marcador not in texto:
                return []

            parte = texto.split(marcador, 1)[1]
            tokens = parte.split()
            eventos = []
            atual = []

            for palavra in tokens:
                atual.append(palavra)

                if "ago" not in palavra.lower():
                    continue

                frase = " ".join(atual).strip()
                atual = []

                if "killed" not in frase or "-" not in frase:
                    continue

                base, tempo = frase.split("-", 1)
                base = base.strip()
                tempo = tempo.strip()

                if base and tempo:
                    eventos.append((base, tempo))

            return eventos

        except requests.RequestException as erro:
            print(f"⚠️ Erro ao buscar PvP de {nome}:", erro)
            return []

    return []


def analisar_pvps():
    """
    Busca somente nos perfis da Virtue.

    O feed é reconstruído em cada ciclo. Isso evita eventos antigos presos no
    cache e garante a ordem correta: menor idade primeiro (4 min, 6 min, 8 min...).
    """
    print("\n🔎 Analisando PvPs da Virtue...\n")

    eventos_random = []
    eventos_peace = []
    eventos_infernal = []

    # Remove apenas a duplicação do MESMO evento visto em perfis diferentes.
    # O índice da linha preserva 2 ou 3 kills idênticas listadas no mesmo perfil.
    vistos_random = set()
    vistos_peace = set()
    vistos_infernal = set()

    for ordem_perfil, nome_norm in enumerate(MEMBROS_VIRTUE):
        # O atraso entre perfis evita disparar dezenas de requisições de uma vez.
        if ordem_perfil > 0:
            time.sleep(ATRASO_ENTRE_PERFIS + random.uniform(0.1, 0.5))

        eventos = pegar_pvp(nome_norm)

        for ordem_linha, (base, tempo) in enumerate(eventos):
            if not dentro_do_limite(tempo):
                continue

            killers, vitima = normalizar_kill(base)
            if not killers or not vitima:
                continue

            killers_norm = [limpar_nome(killer) for killer in killers]
            vitima_norm = limpar_nome(vitima)
            idade_segundos = tempo_para_segundos(tempo)

            killer_virtue = any(k in MEMBROS_VIRTUE for k in killers_norm)
            vitima_virtue = vitima_norm in MEMBROS_VIRTUE

            evento = {
                "killers": killers,
                "victim": vitima,
                "tempo": tempo,
                "idade": idade_segundos,
                "ordem_perfil": ordem_perfil,
                "ordem_linha": ordem_linha,
                "icon": "🔵" if killer_virtue else "🔴",
            }

            # Chave inclui a posição da linha para manter repetições legítimas.
            chave_random = (
                limpar_nome(base),
                tempo.lower(),
                ordem_linha,
            )

            if chave_random not in vistos_random:
                vistos_random.add(chave_random)
                eventos_random.append(evento.copy())

            killer_peace = any(k in MEMBROS_PEACE for k in killers_norm)
            vitima_peace = vitima_norm in MEMBROS_PEACE
            guerra_peace = (
                (killer_virtue and vitima_peace)
                or (killer_peace and vitima_virtue)
            )

            if guerra_peace:
                chave = (limpar_nome(base), tempo.lower(), ordem_linha)
                if chave not in vistos_peace:
                    vistos_peace.add(chave)
                    evento_peace = evento.copy()
                    evento_peace["icon"] = "🔵" if killer_virtue else "🔴"
                    eventos_peace.append(evento_peace)

            killer_infernal = any(k in MEMBROS_INFERNAL for k in killers_norm)
            vitima_infernal = vitima_norm in MEMBROS_INFERNAL
            guerra_infernal = (
                (killer_virtue and vitima_infernal)
                or (killer_infernal and vitima_virtue)
            )

            if guerra_infernal:
                chave = (limpar_nome(base), tempo.lower(), ordem_linha)
                if chave not in vistos_infernal:
                    vistos_infernal.add(chave)
                    evento_infernal = evento.copy()
                    evento_infernal["icon"] = "🔵" if killer_virtue else "🔴"
                    eventos_infernal.append(evento_infernal)

    # Mais recente em cima. Para tempos iguais, mantém a ordem mostrada pelo site.
    chave_ordenacao = lambda e: (
        e["idade"],
        e["ordem_perfil"],
        e["ordem_linha"],
    )

    eventos_random.sort(key=chave_ordenacao)
    eventos_peace.sort(key=chave_ordenacao)
    eventos_infernal.sort(key=chave_ordenacao)

    print(
        f"🧠 Encontrados: Random={len(eventos_random)} | "
        f"Peace={len(eventos_peace)} | Infernal={len(eventos_infernal)}"
    )

    return eventos_peace, eventos_infernal, eventos_random

# =========================
# PAINÉIS
# =========================


def adicionar_eventos(msg, eventos):
    if not eventos:
        return msg + "_Nenhum PvP encontrado._\n"

    for evento in eventos[:MAX_EVENTOS_PAINEL]:
        killers = evento["killers"]
        killers_txt = formatar_killers(killers)
        verbo = verbo_matar(len(killers))

        msg += (
            f'{evento["icon"]} {killers_txt} {verbo} **{evento["victim"]}**\n'
            f'└─ ⏱️ {traduzir_tempo(evento["tempo"])}\n\n'
        )

    return msg


def gerar_painel_guerra(nome_inimigo, emoji, eventos):
    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = "⛓️━━━━━━━━ **WAR STATUS** ━━━━━━━━⛓️\n\n"
    msg += f"🛡️ **Virtue**  ⚔️  **{nome_inimigo}** {emoji}\n"
    msg += f"📌 PvPs registrados nas últimas **{LIMITE_PVP_HORAS} horas**\n\n"
    msg = adicionar_eventos(msg, eventos)
    msg += f"\n🕒 **Última atualização:** {agora}"

    return msg[:2000]


def gerar_painel_random(eventos):
    agora = datetime.now(BRASIL).strftime("%H:%M")

    msg = "☠️━━━━━━ **RANDOM KILLS** ━━━━━━☠️\n\n"
    msg += "📡 Últimos PvPs encontrados nos membros da Virtue\n\n"
    msg = adicionar_eventos(msg, eventos)
    msg += f"\n🕒 **Última atualização:** {agora}"

    return msg[:2000]

# =========================
# LOOP
# =========================


def main():
    print("🔥 Bot PvP com 3 painéis iniciado")

    ids = carregar_ids()
    atualizar_membros()
    ultimo_update_membros = time.time()

    while True:
        try:
            # Atualiza as três listas a cada 10 minutos.
            if time.time() - ultimo_update_membros >= 600:
                atualizar_membros()
                ultimo_update_membros = time.time()

            peace, infernal, random = analisar_pvps()

            painel_peace = gerar_painel_guerra("Peace Killers", "🟥", peace)
            painel_infernal = gerar_painel_guerra("Infernal Cruelty", "👹", infernal)
            painel_random = gerar_painel_random(random)

            # Cada painel possui sua própria mensagem e é editado separadamente.
            atualizar_painel(ids, "peace", painel_peace)
            atualizar_painel(ids, "infernal", painel_infernal)
            atualizar_painel(ids, "random", painel_random)

            time.sleep(INTERVALO)

        except Exception as erro:
            print("❌ Erro no loop principal:", erro)
            time.sleep(60)


if __name__ == "__main__":
    main()
