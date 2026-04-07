import os
import re
import json
import time
import unicodedata
import pandas as pd
import requests

from urllib.parse import urlparse
from decouple import config
from bs4 import BeautifulSoup


SERPER_API_KEY = config("SERPER_API_KEY", default="").strip()

LIMITE_MAPS = 20
LIMITE_INSTAGRAM = 10
PAUSA_ENTRE_REQUISICOES = 1
PAUSA_ENTRE_LINHAS = 2
TIMEOUT = 20
SCORE_MINIMO_INSTAGRAM = 8

COLUNAS_SAIDA = [
    "Fonte",
    "Busca Original",
    "Razão Social",
    "Nome Fantasia",
    "Telefone",
    "Email",
    "WhatsApp",
    "Site",
    "Endereço Completo",
    "Cidade",
    "Estado",
    "CNPJ",
    "Instagram Username",
    "Instagram URL",
    "Bio Instagram",
    "Confiança",
    "Observação",
]




def montar_localizacao_busca(cidade="", estado="", bairro="", cep=""):
    partes = []

    if bairro:
        partes.append(str(bairro).strip())
    if cidade:
        partes.append(str(cidade).strip())
    if estado:
        partes.append(str(estado).strip())
    if cep:
        partes.append(f"CEP {str(cep).strip()}")

    return " - ".join([p for p in partes if p])


def obter_valor_coluna(linha, *nomes):
    for nome in nomes:
        if nome in linha:
            return linha.get(nome, "")
    return ""


def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto


def extrair_contatos_texto(texto):
    if not texto:
        return {
            "telefone": "",
            "email": "",
            "whatsapp": "",
        }

    texto = str(texto)

    telefones = re.findall(
        r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9?\d{4})[-\s]?\d{4}",
        texto,
        flags=re.IGNORECASE,
    )

    emails = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        texto,
        flags=re.IGNORECASE,
    )

    whatsapp_match = re.search(
        r"(?:whatsapp|whats|zap)[^\d]*(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?(?:9?\d{4})[-\s]?\d{4}",
        texto,
        flags=re.IGNORECASE,
    )

    telefone = telefones[0].strip() if telefones else ""
    email = emails[0].strip() if emails else ""
    whatsapp = whatsapp_match.group(0).strip() if whatsapp_match else ""

    return {
        "telefone": telefone,
        "email": email,
        "whatsapp": whatsapp,
    }


def url_eh_perfil_instagram(url):
    if not url:
        return False

    try:
        parsed = urlparse(url)
        dominio = parsed.netloc.lower()
        caminho = parsed.path.lower()

        if "instagram.com" not in dominio:
            return False

        rotas_invalidas = [
            "/p/",
            "/reel/",
            "/reels/",
            "/stories/",
            "/explore/",
            "/tv/",
            "/accounts/",
            "/directory/",
            "/about/",
            "/legal/",
            "/developer/",
            "/challenge/",
        ]

        if any(rota in caminho for rota in rotas_invalidas):
            return False

        partes = [p for p in parsed.path.strip("/").split("/") if p]
        if len(partes) != 1:
            return False

        username = partes[0].strip().lower()

        invalidos = {
            "instagram",
            "accounts",
            "explore",
            "reel",
            "reels",
            "stories",
            "p",
            "tv",
            "about",
            "legal",
            "developer",
            "challenge",
        }

        if username in invalidos:
            return False

        return True

    except Exception:
        return False


def extrair_username_instagram(url):
    if not url_eh_perfil_instagram(url):
        return ""

    try:
        parsed = urlparse(url)
        return parsed.path.strip("/").split("/")[0].strip()
    except Exception:
        return ""


def extrair_dominio_site(site):
    if not site:
        return ""

    try:
        parsed = urlparse(site)
        dominio = parsed.netloc.lower().strip()

        if dominio.startswith("www."):
            dominio = dominio[4:]

        return dominio
    except Exception:
        return ""


def extrair_palavras_servico(servico):
    servico_norm = normalizar_texto(servico)
    if not servico_norm:
        return []

    termos = [p for p in re.split(r"[^a-z0-9]+", servico_norm) if len(p) >= 3]

    compostos = []
    if "link" in termos and "dedicado" in termos:
        compostos.append("link dedicado")
    if "banda" in termos and "larga" in termos:
        compostos.append("banda larga")

    return list(dict.fromkeys(termos + compostos))


def obter_palavras_segmento(servico=""):
    palavras_base = [
        "internet",
        "fibra",
        "fibra optica",
        "wifi",
        "wi-fi",
        "provedor",
        "telecom",
        "banda larga",
        "link dedicado",
        "isp",
        "conexao",
        "conectividade",
        "roteador",
        "dados",
        "rede",
        "redes",
        "ftth",
    ]

    palavras_servico = extrair_palavras_servico(servico)
    return list(dict.fromkeys(palavras_base + palavras_servico))


def obter_palavras_negativas():
    return [
        "advogado",
        "advocacia",
        "direito",
        "sobrancelha",
        "sobrancelhas",
        "cilios",
        "estetica",
        "beleza",
        "salao",
        "salão",
        "barbearia",
        "clinica",
        "clínica",
        "odontologia",
        "dentista",
        "medicina",
        "psicologia",
        "nutricao",
        "nutrição",
        "moda",
        "roupa",
        "loja",
        "make",
        "maquiagem",
        "blog",
        "influencer",
        "personal",
        "coach",
        "fotografia",
        "fotografo",
        "fotógrafo",
        "cantor",
        "cantora",
        "musico",
        "músico",
        "music",
        "vereador",
        "deputado",
        "politica",
        "política",
        "sobrancelhas_design",
        "designer de sobrancelhas",
    ]


def calcular_score_instagram(
    candidato,
    nome_empresa="",
    cidade="",
    estado="",
    site="",
    servico="",
):
    score = 0

    title = normalizar_texto(candidato.get("title", ""))
    snippet = normalizar_texto(candidato.get("snippet", ""))
    username = normalizar_texto(candidato.get("username", ""))
    bio = normalizar_texto(candidato.get("bio", ""))
    link = normalizar_texto(candidato.get("link", ""))

    texto_total = f"{title} {snippet} {bio} {username} {link}"

    nome_empresa_norm = normalizar_texto(nome_empresa)
    cidade_norm = normalizar_texto(cidade)
    estado_norm = normalizar_texto(estado)
    dominio_site = extrair_dominio_site(site)

    palavras_segmento = obter_palavras_segmento(servico)
    palavras_negativas = obter_palavras_negativas()

    if nome_empresa_norm:
        if nome_empresa_norm in title:
            score += 8
        if nome_empresa_norm in snippet:
            score += 6
        if nome_empresa_norm in bio:
            score += 6

        nome_sem_espaco = nome_empresa_norm.replace(" ", "")
        username_limpo = username.replace("_", "").replace(".", "").replace("-", "")
        if nome_sem_espaco and nome_sem_espaco in username_limpo:
            score += 6

        partes_nome = [p for p in nome_empresa_norm.split() if len(p) >= 4]
        for parte in partes_nome:
            if parte in title:
                score += 2
            if parte in snippet:
                score += 1
            if parte in bio:
                score += 1
            if parte in username:
                score += 2

    if cidade_norm:
        if cidade_norm in title:
            score += 1
        if cidade_norm in snippet:
            score += 1
        if cidade_norm in bio:
            score += 1

    if estado_norm:
        if estado_norm in title:
            score += 1
        if estado_norm in snippet:
            score += 1
        if estado_norm in bio:
            score += 1

    if dominio_site:
        if dominio_site in snippet:
            score += 5
        if dominio_site in bio:
            score += 5
        if dominio_site in link:
            score += 3
        if dominio_site in title:
            score += 3

    matches_segmento = 0
    for termo in palavras_segmento:
        if termo and termo in texto_total:
            matches_segmento += 1

    score += min(matches_segmento * 2, 10)

    matches_negativos = 0
    for termo in palavras_negativas:
        if termo in texto_total:
            matches_negativos += 1

    score -= matches_negativos * 6

    if matches_segmento == 0:
        score -= 12

    indicadores_pessoais = 0

    if username:
        if username.count("_") >= 2:
            indicadores_pessoais += 1

        partes_user = [p for p in re.split(r"[._-]+", username) if p]
        if len(partes_user) >= 2 and all(len(p) > 2 for p in partes_user[:2]):
            indicadores_pessoais += 1

    if "oficial" not in texto_total and "empresa" not in texto_total and "telecom" not in texto_total:
        if matches_segmento == 0:
            indicadores_pessoais += 1

    score -= indicadores_pessoais * 3

    return score


def perfil_instagram_aprovado(perfil, servico="", score_minimo=SCORE_MINIMO_INSTAGRAM):
    score = perfil.get("score", 0)

    texto = normalizar_texto(
        f"{perfil.get('title', '')} "
        f"{perfil.get('snippet', '')} "
        f"{perfil.get('bio', '')} "
        f"{perfil.get('username', '')}"
    )

    palavras_segmento = obter_palavras_segmento(servico)
    palavras_negativas = obter_palavras_negativas()

    tem_segmento = any(p in texto for p in palavras_segmento)
    tem_negativo = any(p in texto for p in palavras_negativas)

    return score >= score_minimo and tem_segmento and not tem_negativo


def classificar_confianca(fonte, telefone="", email="", instagram_url="", endereco="", site="", score_instagram=0):
    pontos = 0

    if fonte == "Google Maps":
        pontos += 2
    if telefone:
        pontos += 1
    if email:
        pontos += 1
    if instagram_url:
        pontos += 1
    if endereco:
        pontos += 1
    if site:
        pontos += 1

    if score_instagram >= 8:
        pontos += 2
    elif score_instagram >= 4:
        pontos += 1

    if pontos >= 5:
        return "Alta"
    if pontos >= 3:
        return "Média"
    return "Baixa"


def criar_registro_base(query, cidade, estado, fonte=""):
    return {
        "Fonte": fonte,
        "Busca Original": query,
        "Razão Social": "",
        "Nome Fantasia": "",
        "Telefone": "",
        "Email": "",
        "WhatsApp": "",
        "Site": "",
        "Endereço Completo": "",
        "Cidade": cidade,
        "Estado": estado,
        "CNPJ": "",
        "Instagram Username": "",
        "Instagram URL": "",
        "Bio Instagram": "",
        "Confiança": "",
        "Observação": "",
    }


def buscar_no_google_maps(servico, cidade, estado, bairro="", cep=""):
    url = "https://google.serper.dev/places"
    localizacao = montar_localizacao_busca(cidade=cidade, estado=estado, bairro=bairro, cep=cep)
    query = f"{servico} em {localizacao}" if localizacao else str(servico).strip()

    payload = {
        "q": query,
        "gl": "br",
        "hl": "pt-br",
    }

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        response.raise_for_status()

        dados = response.json()
        lugares = dados.get("places", [])
        return lugares[:LIMITE_MAPS]

    except requests.RequestException as e:
        print(f"Erro ao consultar Google Maps para '{query}': {e}")
        return []
    except Exception as e:
        print(f"Erro inesperado no Google Maps para '{query}': {e}")
        return []


def buscar_instagram_por_empresa(nome_empresa, cidade, estado, site="", servico="", bairro="", cep=""):
    url = "https://google.serper.dev/search"
    localizacao = montar_localizacao_busca(cidade=cidade, estado=estado, bairro=bairro, cep=cep)

    query_busca = (
        f'site:instagram.com "{nome_empresa}" "{localizacao}" '
        f'"{servico}" '
        f'-inurl:/p/ -inurl:/reel/ -inurl:/reels/ -inurl:/stories/ -inurl:/explore/'
    )

    payload = {
        "q": query_busca,
        "gl": "br",
        "hl": "pt-br",
        "num": LIMITE_INSTAGRAM,
    }

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    resultados = []

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        response.raise_for_status()

        dados = response.json()
        organicos = dados.get("organic", [])

        for item in organicos:
            link = item.get("link", "").strip()
            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()

            if not url_eh_perfil_instagram(link):
                continue

            username = extrair_username_instagram(link)
            if not username:
                continue

            candidato = {
                "title": title,
                "link": link,
                "snippet": snippet,
                "username": username,
            }

            candidato["score"] = calcular_score_instagram(
                candidato,
                nome_empresa=nome_empresa,
                cidade=cidade,
                estado=estado,
                site=site,
                servico=servico,
            )

            resultados.append(candidato)

        resultados.sort(key=lambda x: x.get("score", 0), reverse=True)
        return resultados

    except requests.RequestException as e:
        print(f"Erro ao consultar Instagram por empresa '{nome_empresa}': {e}")
        return []
    except Exception as e:
        print(f"Erro inesperado ao buscar Instagram por empresa '{nome_empresa}': {e}")
        return []


def buscar_instagram_via_google_fallback(servico, cidade, estado, bairro="", cep=""):
    url = "https://google.serper.dev/search"
    localizacao = montar_localizacao_busca(cidade=cidade, estado=estado, bairro=bairro, cep=cep)

    query_busca = (
        f'site:instagram.com "{servico}" "{localizacao}" '
        f'-inurl:/p/ -inurl:/reel/ -inurl:/reels/ -inurl:/stories/ -inurl:/explore/'
    )

    payload = {
        "q": query_busca,
        "gl": "br",
        "hl": "pt-br",
        "num": LIMITE_INSTAGRAM,
    }

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    resultados = []

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        response.raise_for_status()

        dados = response.json()
        organicos = dados.get("organic", [])

        for item in organicos:
            link = item.get("link", "").strip()
            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()

            if not url_eh_perfil_instagram(link):
                continue

            username = extrair_username_instagram(link)
            if not username:
                continue

            resultados.append({
                "title": title,
                "link": link,
                "snippet": snippet,
                "username": username,
                "score": 0,
            })

        return resultados

    except requests.RequestException as e:
        print(f"Erro ao consultar Instagram fallback para '{servico} / {cidade} / {estado}': {e}")
        return []
    except Exception as e:
        print(f"Erro inesperado no fallback de Instagram para '{servico} / {cidade} / {estado}': {e}")
        return []


def enriquecer_perfil_instagram(url_perfil):
    if not url_perfil:
        return {
            "bio": "",
            "telefone": "",
            "email": "",
            "whatsapp": "",
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url_perfil, headers=headers, timeout=TIMEOUT)
        if response.status_code != 200:
            return {
                "bio": "",
                "telefone": "",
                "email": "",
                "whatsapp": "",
            }

        soup = BeautifulSoup(response.text, "html.parser")

        bio = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            bio = meta_desc.get("content", "").strip()

        if not bio:
            og_desc = soup.find("meta", attrs={"property": "og:description"})
            if og_desc and og_desc.get("content"):
                bio = og_desc.get("content", "").strip()

        contatos = extrair_contatos_texto(bio)

        return {
            "bio": bio,
            "telefone": contatos.get("telefone", ""),
            "email": contatos.get("email", ""),
            "whatsapp": contatos.get("whatsapp", ""),
        }

    except Exception:
        return {
            "bio": "",
            "telefone": "",
            "email": "",
            "whatsapp": "",
        }


def escolher_melhor_perfil_instagram(perfis, nome_empresa, cidade, estado, site="", servico=""):
    if not perfis:
        return None

    melhor = None
    melhor_score = -999

    for perfil in perfis:
        enriquecimento = enriquecer_perfil_instagram(perfil.get("link", ""))
        perfil_enriquecido = dict(perfil)
        perfil_enriquecido.update(enriquecimento)

        score_final = calcular_score_instagram(
            perfil_enriquecido,
            nome_empresa=nome_empresa,
            cidade=cidade,
            estado=estado,
            site=site,
            servico=servico,
        )

        perfil_enriquecido["score"] = score_final

        if not perfil_instagram_aprovado(
            perfil_enriquecido,
            servico=servico,
            score_minimo=SCORE_MINIMO_INSTAGRAM,
        ):
            time.sleep(PAUSA_ENTRE_REQUISICOES)
            continue

        if score_final > melhor_score:
            melhor_score = score_final
            melhor = perfil_enriquecido

        time.sleep(PAUSA_ENTRE_REQUISICOES)

    return melhor


def deduplicar_resultados(resultados):
    vistos = set()
    saida = []

    for item in resultados:
        chave = (
            normalizar_texto(item.get("Fonte", "")),
            normalizar_texto(item.get("Razão Social", "") or item.get("Nome Fantasia", "")),
            normalizar_texto(item.get("Telefone", "")),
            normalizar_texto(item.get("Site", "")),
            normalizar_texto(item.get("Endereço Completo", "")),
            normalizar_texto(item.get("Instagram URL", "")),
            normalizar_texto(item.get("Cidade", "")),
            normalizar_texto(item.get("Estado", "")),
        )

        if chave in vistos:
            continue

        vistos.add(chave)
        saida.append(item)

    return saida


def persistir_resultados_se_callback(resultados, salvar_no_banco_fn):
    if not salvar_no_banco_fn:
        return

    for registro in resultados:
        try:
            salvar_no_banco_fn(registro)
        except Exception as e:
            print(f"Erro ao salvar registro no banco: {e}")


def processar_planilha(caminho_entrada, caminho_saida, salvar_no_banco_fn=None):
    if not SERPER_API_KEY:
        raise ValueError("A variável SERPER_API_KEY não foi encontrada no .env.")

    if not os.path.exists(caminho_entrada):
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {caminho_entrada}")

    df = pd.read_excel(caminho_entrada)

    colunas_obrigatorias = {"Cidade", "Estado"}
    faltando = colunas_obrigatorias - set(df.columns)
    possui_coluna_servico = "Serviço" in df.columns or "Servi?o" in df.columns

    if faltando or not possui_coluna_servico:
        colunas_faltando = sorted(faltando)
        if not possui_coluna_servico:
            colunas_faltando.insert(0, "Serviço")
        raise ValueError(
            "A planilha precisa conter as colunas: Serviço, Cidade e Estado. "
            f"Faltando: {', '.join(colunas_faltando)}"
        )

    resultados = []

    print(f"Iniciando processamento de {len(df)} linha(s)...")

    for index, linha in df.iterrows():
        servico = str(obter_valor_coluna(linha, "Serviço", "Servi?o")).strip()
        cidade = str(linha.get("Cidade", "")).strip()
        estado = str(linha.get("Estado", "")).strip()
        bairro = str(linha.get("Bairro", "")).strip()
        cep = str(linha.get("CEP", "")).strip()

        if not servico or not cidade or not estado:
            print(f"[{index + 1}/{len(df)}] Linha ignorada por falta de dados.")
            continue

        localizacao = montar_localizacao_busca(cidade=cidade, estado=estado, bairro=bairro, cep=cep)
        query = f"{servico} em {localizacao}" if localizacao else str(servico).strip()
        print(f"\n[{index + 1}/{len(df)}] Processando: {query}")

        registros_linha = []
        total_instagrams_enriquecidos = 0
        total_fallback_instagram = 0

        resultados_maps = buscar_no_google_maps(servico, cidade, estado, bairro=bairro, cep=cep)
        print(f"   Maps retornou: {len(resultados_maps)} registro(s)")

        time.sleep(PAUSA_ENTRE_REQUISICOES)

        if resultados_maps:
            for fornecedor in resultados_maps:
                nome_empresa = fornecedor.get("title", "") or "Não informado"
                telefone_maps = fornecedor.get("phoneNumber", "") or ""
                site_maps = fornecedor.get("website", "") or ""
                endereco_maps = fornecedor.get("address", "") or ""

                registro = criar_registro_base(query, cidade, estado, fonte="Google Maps")
                registro["Razão Social"] = nome_empresa
                registro["Nome Fantasia"] = nome_empresa
                registro["Telefone"] = telefone_maps
                registro["Site"] = site_maps
                registro["Endereço Completo"] = endereco_maps
                registro["Observação"] = "Resultado obtido via Google Maps"

                perfis_insta = buscar_instagram_por_empresa(
                    nome_empresa=nome_empresa,
                    cidade=cidade,
                    estado=estado,
                    site=site_maps,
                    servico=servico,
                    bairro=bairro,
                    cep=cep,
                )

                print(f"   Instagram para '{nome_empresa}': {len(perfis_insta)} perfil(is)")

                melhor_score = 0

                if perfis_insta:
                    melhor_perfil = escolher_melhor_perfil_instagram(
                        perfis=perfis_insta,
                        nome_empresa=nome_empresa,
                        cidade=cidade,
                        estado=estado,
                        site=site_maps,
                        servico=servico,
                    )

                    if melhor_perfil:
                        melhor_score = melhor_perfil.get("score", 0)

                        registro["Instagram Username"] = melhor_perfil.get("username", "") or ""
                        registro["Instagram URL"] = melhor_perfil.get("link", "") or ""
                        registro["Bio Instagram"] = melhor_perfil.get("bio", "") or ""

                        if not registro["Telefone"]:
                            registro["Telefone"] = melhor_perfil.get("telefone", "") or ""
                        if not registro["Email"]:
                            registro["Email"] = melhor_perfil.get("email", "") or ""
                        if not registro["WhatsApp"]:
                            registro["WhatsApp"] = melhor_perfil.get("whatsapp", "") or ""

                        total_instagrams_enriquecidos += 1
                        registro["Observação"] = "Resultado obtido via Google Maps com enriquecimento de Instagram"
                    else:
                        registro["Observação"] = (
                            "Resultado obtido via Google Maps; Instagram encontrado, "
                            "mas descartado pelo filtro de relevância"
                        )

                registro["Confiança"] = classificar_confianca(
                    fonte="Google Maps",
                    telefone=registro["Telefone"],
                    email=registro["Email"],
                    instagram_url=registro["Instagram URL"],
                    endereco=registro["Endereço Completo"],
                    site=registro["Site"],
                    score_instagram=melhor_score,
                )

                registros_linha.append(registro)
                time.sleep(PAUSA_ENTRE_REQUISICOES)

        else:
            perfis_fallback = buscar_instagram_via_google_fallback(servico, cidade, estado, bairro=bairro, cep=cep)
            print(f"   Fallback Instagram retornou: {len(perfis_fallback)} perfil(is)")

            for perfil in perfis_fallback:
                enriquecimento = enriquecer_perfil_instagram(perfil.get("link", ""))
                perfil_enriquecido = dict(perfil)
                perfil_enriquecido.update(enriquecimento)

                score_fallback = calcular_score_instagram(
                    perfil_enriquecido,
                    nome_empresa=servico,
                    cidade=cidade,
                    estado=estado,
                    site="",
                    servico=servico,
                )

                perfil_enriquecido["score"] = score_fallback

                if not perfil_instagram_aprovado(
                    perfil_enriquecido,
                    servico=servico,
                    score_minimo=SCORE_MINIMO_INSTAGRAM,
                ):
                    time.sleep(PAUSA_ENTRE_REQUISICOES)
                    continue

                registro = criar_registro_base(query, cidade, estado, fonte="Instagram Fallback")
                nome_fallback = perfil.get("title", "") or perfil.get("username", "") or "Perfil Instagram"

                registro["Razão Social"] = nome_fallback
                registro["Nome Fantasia"] = nome_fallback
                registro["Instagram Username"] = perfil.get("username", "") or ""
                registro["Instagram URL"] = perfil.get("link", "") or ""
                registro["Bio Instagram"] = perfil_enriquecido.get("bio", "") or perfil.get("snippet", "") or ""
                registro["Telefone"] = perfil_enriquecido.get("telefone", "") or ""
                registro["Email"] = perfil_enriquecido.get("email", "") or ""
                registro["WhatsApp"] = perfil_enriquecido.get("whatsapp", "") or ""
                registro["Confiança"] = classificar_confianca(
                    fonte="Instagram Fallback",
                    telefone=registro["Telefone"],
                    email=registro["Email"],
                    instagram_url=registro["Instagram URL"],
                    endereco=registro["Endereço Completo"],
                    site=registro["Site"],
                    score_instagram=score_fallback,
                )
                registro["Observação"] = "Registro criado a partir do fallback de Instagram"

                registros_linha.append(registro)
                total_fallback_instagram += 1
                time.sleep(PAUSA_ENTRE_REQUISICOES)

        resultados.extend(registros_linha)

        print(f"   Instagrams enriquecidos nesta linha: {total_instagrams_enriquecidos}")
        print(f"   Registros fallback nesta linha: {total_fallback_instagram}")
        print(f"   Total adicionado nesta linha: {len(registros_linha)}")

        time.sleep(PAUSA_ENTRE_LINHAS)

    total_antes_dedup = len(resultados)
    resultados = deduplicar_resultados(resultados)
    total_depois_dedup = len(resultados)

    print("\nResumo final:")
    print(f"   Total antes da deduplicação: {total_antes_dedup}")
    print(f"   Total depois da deduplicação: {total_depois_dedup}")

    df_final = pd.DataFrame(resultados)

    if df_final.empty:
        df_final = pd.DataFrame(columns=COLUNAS_SAIDA)
    else:
        for coluna in COLUNAS_SAIDA:
            if coluna not in df_final.columns:
                df_final[coluna] = ""
        df_final = df_final[COLUNAS_SAIDA]

    df_final.to_excel(caminho_saida, index=False)

    persistir_resultados_se_callback(resultados, salvar_no_banco_fn)

    print(f"\nAutomação concluída.")
    print(f"Total de fornecedores encontrados: {len(df_final)}")
    print(f"Arquivo salvo em: {caminho_saida}")

    return resultados


if __name__ == "__main__":
    caminho_entrada = "teste_entrada.xlsx"
    caminho_saida = "teste_saida.xlsx"

    if not os.path.exists(caminho_entrada):
        df_teste = pd.DataFrame({
            "Serviço": ["Provedor de Internet", "Link Dedicado"],
            "Cidade": ["Fortaleza", "Eusébio"],
            "Estado": ["CE", "CE"],
            "Bairro": ["Centro", "Guaribas"],
            "CEP": ["60000-000", "61760-000"],
        })
        df_teste.to_excel(caminho_entrada, index=False)

    resultados = processar_planilha(caminho_entrada, caminho_saida)
    print(f"Registros processados: {len(resultados)}")
