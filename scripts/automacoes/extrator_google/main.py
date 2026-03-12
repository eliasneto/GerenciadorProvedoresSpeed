import os
import sys
import time
import random
import re
import urllib.parse
import django
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURAÇÃO DJANGO ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from leads.models import Lead 
from automacoes.models import Automacao

def iniciar_driver():
    options = Options()
    if sys.platform.startswith('linux'):
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
    else:
        options.add_argument("--start-maximized")

    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def investigar_dados_profundo(driver, nome_empresa, site_url):
    email, cnpj = None, None
    site_oficial = site_url

    if site_url and 'google.com' not in site_url:
        try:
            driver.execute_script(f"window.open('{site_url}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(5)
            corpo = driver.page_source
            e_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', corpo)
            if e_match: email = e_match.group(0)
            c_match = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', corpo)
            if c_match: cnpj = c_match.group(0)
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except: pass
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

    # FALLBACK DUCKDUCKGO
    if not cnpj or not site_oficial:
        try:
            query_ddg = f"https://html.duckduckgo.com/html/?q=empresa+{nome_empresa.replace(' ', '+')}"
            driver.execute_script(f"window.open('{query_ddg}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
            
            if not site_oficial:
                try:
                    links_ddg = driver.find_elements(By.CSS_SELECTOR, "a.result__url")
                    for lnk in links_ddg:
                        href = lnk.get_attribute("href")
                        if href and "cnpj" not in href and "jusbrasil" not in href and "instagram" not in href and "facebook" not in href:
                            site_oficial = href
                            break
                except: pass

            c_match = re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', driver.page_source)
            if c_match: cnpj = c_match.group(0)
            
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except: pass
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

    return email, cnpj, site_oficial

def realizar_scroll(driver):
    try:
        painel_lista = driver.find_element(By.CSS_SELECTOR, "div[role='feed'], div[aria-label^='Resultados']")
        for _ in range(3):
            driver.execute_script(f"arguments[0].scrollTop += {random.randint(600, 1000)}", painel_lista)
            time.sleep(random.uniform(2.0, 3.5))
    except: pass

def extrair_leads(caminho_excel, automacao_id):
    caminho_abs = os.path.normpath(os.path.join(BASE_DIR, 'media', 'automacoes', 'entradas', os.path.basename(caminho_excel)))
    if not os.path.exists(caminho_abs):
        caminho_abs = os.path.normpath(os.path.join(BASE_DIR, 'media', os.path.basename(caminho_excel)))

    robo = Automacao.objects.get(id=automacao_id)
    robo.status = 'RODANDO'
    robo.progresso = 2
    robo.save()

    driver = iniciar_driver()
    leads_novos = 0
    
    try:
        df = pd.read_excel(caminho_abs, header=None)
        total_linhas = len(df)

        for index, linha in df.iterrows():
            progresso_base = int((index / total_linhas) * 100)
            
            servico = str(linha[0]).strip()
            bairro = str(linha[1]).strip() if len(linha) > 1 and pd.notna(linha[1]) else ""
            cidade = str(linha[2]).strip() if len(linha) > 2 else ""
            uf = str(linha[3]).strip() if len(linha) > 3 else "CE"

            if servico.lower() in ['servico', 'serviço', 'nan']: continue

            q = f"{servico} em {bairro}, {cidade}" if bairro and bairro.lower() != 'nan' else f"{servico} em {cidade}"
            if "- CE" not in q and "- BA" not in q: q += f" - {uf}"
            
            print(f"\n🔎 [{progresso_base}%] Buscando: {q}")
            driver.get(f"https://www.google.com.br/maps/search/{q.replace(' ', '+')}")
            
            time.sleep(random.uniform(6.0, 8.0))
            realizar_scroll(driver)
            
            cards = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc, div[role='article']")
            total_cards = len(cards[:20])
            print(f"👀 Encontrou {total_cards} empresas.")

            for idx_card, card in enumerate(cards[:20]):
                sub_fatia = (100 / total_linhas)
                robo.progresso = min(int(progresso_base + ((idx_card / total_cards) * sub_fatia)), 99)
                robo.save()

                try:
                    nome = card.get_attribute("aria-label")
                    if not nome: continue
                    
                    if Lead.objects.filter(razao_social=nome, cidade=cidade.title()).exists():
                        print(f"⏩ Pulando (Já existe): {nome}")
                        continue

                    # Clica na empresa e dá um tempo MÍNIMO para a animação do Maps descarregar os dados velhos
                    driver.execute_script("arguments[0].click();", card)
                    time.sleep(1.5) 
                    
                    try:
                        # NOVA LÓGICA: Espera que o Título (h1) do painel lateral atualize para o NOME da nova empresa.
                        # Usa o primeiro nome para evitar falhas com aspas ou caracteres estranhos.
                        primeiro_nome = nome.split()[0].replace("'", "").replace('"', "")
                        WebDriverWait(driver, 8).until(
                            EC.presence_of_element_located((By.XPATH, f"//h1[contains(text(), '{primeiro_nome}')]"))
                        )
                        time.sleep(1) # Extra segurança após a confirmação visual
                    except:
                        time.sleep(4) # Fallback se o título for muito estranho e falhar o XPATH

                    tel, site = "Não informado", None
                    
                    # 1. TENTA ACHAR O SITE
                    try:
                        site_element = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                        site = site_element.get_attribute("href")
                    except:
                        try:
                            links_painel = driver.find_elements(By.CSS_SELECTOR, "div[role='main'] a[href^='http']")
                            for lnk in links_painel:
                                h = lnk.get_attribute("href")
                                if h and "google.com" not in h:
                                    site = h
                                    break
                        except: pass

                    if site and "google.com/url" in site:
                        try:
                            parsed = urllib.parse.urlparse(site)
                            site = urllib.parse.parse_qs(parsed.query).get('q', [site])[0]
                        except: pass

                    # 2. TENTA ACHAR O TELEFONE
                    try:
                        btn_tel = driver.find_element(By.CSS_SELECTOR, "button[data-item-id^='phone:'], button[data-tooltip*='Copiar número']")
                        tel_raw = btn_tel.get_attribute("aria-label")
                        if tel_raw: tel = tel_raw.replace("Telefone: ", "").replace("Phone: ", "").strip()
                        else: tel = btn_tel.text
                    except:
                        try:
                            painel_inteiro = driver.find_element(By.CSS_SELECTOR, "div[role='main']").text
                            phone_match = re.search(r'\(?\d{2}\)?\s?\d{4,5}-?\d{4}', painel_inteiro)
                            if phone_match:
                                tel = phone_match.group(0).strip()
                        except: pass

                    print(f"   ↳ Lendo Maps -> Tel: {tel} | Site: {'Sim' if site else 'Não'}")

                    # 3. INVESTIGAÇÃO PROFUNDA
                    email, cnpj, site_profundo = investigar_dados_profundo(driver, nome, site)
                    
                    if not site and site_profundo:
                        site = site_profundo

                    Lead.objects.create(
                        razao_social=nome, nome_fantasia=nome, cnpj_cpf=cnpj,
                        telefone=tel, email=email, site=site,
                        endereco=f"Bairro: {bairro}" if bairro and bairro != 'nan' else None,
                        cidade=cidade.title(), estado=uf.upper()[:2], status='novo'
                    )
                    leads_novos += 1
                    print(f"✅ SALVO: {nome} | CNPJ: {cnpj or '---'} | Site: {site or '---'}")

                except Exception as e:
                    continue

        robo.status = 'CONCLUIDO'
        robo.progresso = 100
        robo.save()
        print(f"\n🏁 Fim da execução! {leads_novos} novos leads salvos.")

    except Exception as e:
        print(f"❌ Erro Fatal: {e}")
        robo.status = 'ERRO'
        robo.save()
    finally:
        driver.quit()
        try:
            if os.path.exists(caminho_abs): os.remove(caminho_abs)
        except: pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='Excel')
    parser.add_argument('--id', help='ID')
    args = parser.parse_args()
    if args.input and args.id:
        extrair_leads(args.input, args.id)