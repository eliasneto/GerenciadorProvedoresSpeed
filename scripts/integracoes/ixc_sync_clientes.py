"""Logica compartilhada de sincronizacao de clientes IXC -> Django.

Usado por ixc_api.py (carga total) e ixc_api_incremental.py (carga
incremental). Toda comunicacao HTTP com o IXC passa pelo IXCClient
(apps/core/ixc_client.py); nenhum modulo deve reimplementar
o acesso HTTP ao IXC (ADR-005, PO-022).
"""
import unicodedata

from tqdm import tqdm

from apps.clientes.models import Cliente, Endereco, LogAlteracaoIXC
from apps.integracoes.ixc.client import IXCClient


_ixc_client_instance = None


def _get_ixc_client():
    """Instancia o IXCClient sob demanda (nao na importacao do modulo), para
    que este arquivo possa ser importado em testes sem exigir IXC_TOKEN."""
    global _ixc_client_instance
    if _ixc_client_instance is None:
        _ixc_client_instance = IXCClient()
    return _ixc_client_instance


UF_SIGLAS_VALIDAS = {
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
    'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
    'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
}

UF_POR_NOME = {
    'ACRE': 'AC',
    'ALAGOAS': 'AL',
    'AMAPA': 'AP',
    'AMAZONAS': 'AM',
    'BAHIA': 'BA',
    'CEARA': 'CE',
    'DISTRITO FEDERAL': 'DF',
    'ESPIRITO SANTO': 'ES',
    'GOIAS': 'GO',
    'MARANHAO': 'MA',
    'MATO GROSSO': 'MT',
    'MATO GROSSO DO SUL': 'MS',
    'MINAS GERAIS': 'MG',
    'PARA': 'PA',
    'PARAIBA': 'PB',
    'PARANA': 'PR',
    'PERNAMBUCO': 'PE',
    'PIAUI': 'PI',
    'RIO DE JANEIRO': 'RJ',
    'RIO GRANDE DO NORTE': 'RN',
    'RIO GRANDE DO SUL': 'RS',
    'RONDONIA': 'RO',
    'RORAIMA': 'RR',
    'SANTA CATARINA': 'SC',
    'SAO PAULO': 'SP',
    'SERGIPE': 'SE',
    'TOCANTINS': 'TO',
}

UF_POR_CODIGO_IBGE = {
    '12': 'AC', '27': 'AL', '16': 'AP', '13': 'AM', '29': 'BA', '23': 'CE',
    '53': 'DF', '32': 'ES', '52': 'GO', '21': 'MA', '51': 'MT', '50': 'MS',
    '31': 'MG', '15': 'PA', '25': 'PB', '41': 'PR', '26': 'PE', '22': 'PI',
    '33': 'RJ', '24': 'RN', '43': 'RS', '11': 'RO', '14': 'RR', '42': 'SC',
    '35': 'SP', '28': 'SE', '17': 'TO',
}


def consultar_ixc(tabela, payload):
    """Consulta o IXC via IXCClient. Retorna o corpo (dict) ou None em falha."""
    status_code, body = _get_ixc_client().listar(tabela, payload)
    if status_code is None or not (200 <= status_code < 300):
        return None
    if not isinstance(body, dict) or 'raw' in body:
        return None
    return body


def extrair_campos_tecnicos_obs(obs_texto):
    campos = {
        'velocidade': '',
        'tipo_acesso': '',
        'ipv4_bloco': '',
        'dupla_abordagem': '',
        'entrega_rb': '',
    }

    if not obs_texto:
        return campos

    mapa = {
        'VELOCIDADE': 'velocidade',
        'TIPO DE ACESSO': 'tipo_acesso',
        'BLOCO IP': 'ipv4_bloco',
        'DUPLA ABORDAGEM': 'dupla_abordagem',
        'ENTREGA RB': 'entrega_rb',
    }

    for linha in str(obs_texto).splitlines():
        linha_limpa = linha.strip()
        if ':' not in linha_limpa:
            continue
        chave_bruta, valor_bruto = linha_limpa.split(':', 1)
        chave = chave_bruta.strip().upper()
        destino = mapa.get(chave)
        if destino:
            campos[destino] = valor_bruto.strip()

    return campos


def remover_acentos(valor):
    texto = str(valor or '').strip()
    if not texto:
        return ''
    return ''.join(
        caractere for caractere in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(caractere)
    )


def normalizar_uf(valor, padrao='', mapa_estados=None):
    bruto = str(valor or '').strip()
    if not bruto:
        return padrao

    uf = bruto.upper()
    if uf in UF_SIGLAS_VALIDAS:
        return uf

    if bruto.isdigit() and mapa_estados:
        uf_mapeada = str(mapa_estados.get(bruto) or '').strip().upper()
        if uf_mapeada in UF_SIGLAS_VALIDAS:
            return uf_mapeada

    uf_por_nome = UF_POR_NOME.get(remover_acentos(bruto).upper())
    if uf_por_nome:
        return uf_por_nome

    return padrao


def resolver_uf_por_ibge(valor):
    codigo = ''.join(ch for ch in str(valor or '').strip() if ch.isdigit())
    if len(codigo) >= 2:
        return UF_POR_CODIGO_IBGE.get(codigo[:2], '')
    return ''


def resolver_cidade_ixc(valor_cidade, mapa_cidades, mapa_estados=None):
    cidade_bruta = str(valor_cidade or '').strip()
    if not cidade_bruta:
        return '', '', ''

    if cidade_bruta.isdigit():
        cidade_info = mapa_cidades.get(cidade_bruta) or {}
        cidade_nome = str(cidade_info.get('nome') or '').strip()
        cidade_uf = (
            normalizar_uf(cidade_info.get('uf'), mapa_estados=mapa_estados)
            or resolver_uf_por_ibge(cidade_info.get('ibge'))
        )
        if cidade_nome:
            return cidade_nome, cidade_bruta, cidade_uf

        cidade_detalhe = consultar_ixc(f"cidade/{cidade_bruta}", {})
        if cidade_detalhe:
            cidade_nome = (
                cidade_detalhe.get('cidade')
                or cidade_detalhe.get('nome')
                or cidade_detalhe.get('municipio')
                or cidade_detalhe.get('descricao')
                or ''
            )
            cidade_nome = str(cidade_nome).strip()
            cidade_uf = (
                normalizar_uf(
                    cidade_detalhe.get('uf') or cidade_detalhe.get('estado'),
                    mapa_estados=mapa_estados,
                )
                or resolver_uf_por_ibge(
                    cidade_detalhe.get('cod_ibge')
                    or cidade_detalhe.get('codigo_ibge')
                    or cidade_detalhe.get('ibge')
                )
            )
            if cidade_nome:
                mapa_cidades[cidade_bruta] = {
                    'nome': cidade_nome,
                    'uf': cidade_uf,
                    'ibge': cidade_detalhe.get('cod_ibge') or cidade_detalhe.get('codigo_ibge') or cidade_detalhe.get('ibge') or '',
                }
                return cidade_nome, cidade_bruta, cidade_uf

        return '', cidade_bruta, ''

    return cidade_bruta, '', ''


def resolver_endereco_login(login_data, contrato_data, mapa_cidades, mapa_estados=None):
    endereco_login = str(login_data.get('endereco') or '').strip()
    numero_login = str(login_data.get('numero') or '').strip()
    bairro_login = str(login_data.get('bairro') or '').strip()
    cidade_login = str(login_data.get('cidade') or '').strip()
    estado_login = str(login_data.get('uf') or login_data.get('estado') or '').strip()
    cep_login = str(login_data.get('cep') or '').strip()

    usa_endereco_login = any(
        [endereco_login, numero_login, bairro_login, cidade_login, estado_login, cep_login]
    )

    if usa_endereco_login:
        cidade_nome, cidade_id_ixc, cidade_uf = resolver_cidade_ixc(
            cidade_login,
            mapa_cidades,
            mapa_estados=mapa_estados,
        )
        return {
            'cep': cep_login,
            'logradouro': endereco_login or 'Nao informado',
            'numero': numero_login or 'S/N',
            'bairro': bairro_login,
            'cidade': cidade_nome,
            'cidade_id_ixc': cidade_id_ixc,
            'estado': normalizar_uf(estado_login, mapa_estados=mapa_estados) or cidade_uf or 'CE',
        }

    cidade_nome_contrato, cidade_id_ixc_contrato, cidade_uf_contrato = resolver_cidade_ixc(
        contrato_data.get('cidade', ''),
        mapa_cidades,
        mapa_estados=mapa_estados,
    )
    return {
        'cep': str(contrato_data.get('cep') or '').strip(),
        'logradouro': contrato_data.get('endereco') or 'Nao informado',
        'numero': contrato_data.get('numero') or 'S/N',
        'bairro': contrato_data.get('bairro', ''),
        'cidade': cidade_nome_contrato,
        'cidade_id_ixc': cidade_id_ixc_contrato,
        'estado': normalizar_uf(contrato_data.get('uf'), mapa_estados=mapa_estados) or cidade_uf_contrato or 'CE',
    }


def buscar_mapa_filiais():
    print("Mapeando nomes das filiais no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "100"}
    res = consultar_ixc("filial", payload)
    mapa = {}
    if res and 'registros' in res:
        for f in res['registros']:
            mapa[str(f['id'])] = f.get('razao') or f.get('filial') or f"Filial {f['id']}"
    return mapa


def buscar_mapa_estados():
    print("Mapeando siglas dos estados no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "100"}
    res = consultar_ixc("estado", payload)
    mapa = {}
    if res and 'registros' in res:
        for estado in res['registros']:
            estado_id = str(estado.get('id') or '').strip()
            sigla = normalizar_uf(
                estado.get('uf') or estado.get('sigla') or estado.get('abreviacao'),
            ) or normalizar_uf(estado.get('estado') or estado.get('nome'))
            if estado_id and sigla:
                mapa[estado_id] = sigla
    return mapa


def buscar_mapa_cidades(mapa_estados=None):
    print("Mapeando nomes das cidades no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "10000"}
    res = consultar_ixc("cidade", payload)
    mapa = {}
    if res and 'registros' in res:
        for cidade in res['registros']:
            cidade_id = str(cidade.get('id') or '').strip()
            cidade_nome = (
                cidade.get('cidade')
                or cidade.get('nome')
                or cidade.get('municipio')
                or cidade.get('descricao')
                or ''
            )
            if cidade_id:
                mapa[cidade_id] = {
                    'nome': str(cidade_nome).strip(),
                    'uf': normalizar_uf(
                        cidade.get('uf') or cidade.get('estado'),
                        mapa_estados=mapa_estados,
                    ) or resolver_uf_por_ibge(
                        cidade.get('cod_ibge') or cidade.get('codigo_ibge') or cidade.get('ibge')
                    ),
                    'ibge': cidade.get('cod_ibge') or cidade.get('codigo_ibge') or cidade.get('ibge') or '',
                }
    return mapa


def _normalizar_contratos(registros_brutos):
    """Normaliza registros crus de `cliente_contrato` para o formato interno
    (id_contrato/filial_id/agente_id), usado tanto pela carga total quanto
    pela incremental."""
    contratos = []
    for c in registros_brutos or []:
        contratos.append({
            "id_contrato": c['id'],
            "status": c.get('status', 'A'),
            "endereco": c.get('endereco', ''),
            "numero": c.get('numero', 'S/N'),
            "bairro": c.get('bairro', ''),
            "cidade": c.get('cidade', ''),
            "uf": c.get('uf', 'CE'),
            "filial_id": str(c.get('id_filial', '')),
            "agente_id": c.get('vendedor', ''),
        })
    return contratos


def _normalizar_login(l):
    """Normaliza um registro cru de `radusuarios` para o formato interno
    (chave `circuit_id`), usado tanto pela carga total quanto pela
    incremental."""
    return {
        "id_login": str(l.get('id') or '').strip(),
        "id_contrato": l.get('id_contrato', ''),
        "login": l['login'],
        "ativo": l.get('ativo', 'S'),
        "circuit_id": str(l.get('agent_circuit_id') or '').strip(),
        "obs": l.get('obs') or l.get('observacao') or '',
        "endereco": l.get('endereco') or '',
        "numero": l.get('numero') or '',
        "bairro": l.get('bairro') or '',
        "cidade": l.get('cidade') or '',
        "uf": l.get('uf') or l.get('estado') or '',
        "cep": l.get('cep') or '',
    }


def extrair_todos_os_clientes(historico):
    """Carga total: percorre todos os clientes ativos no IXC, paginando."""
    pagina_atual = 1
    registros_por_pagina = 50
    base_de_dados_local = []

    res_total = consultar_ixc("cliente", {"qtype": "ativo", "query": "S", "oper": "=", "rp": "1"})
    total_no_ixc = int(res_total.get('total', 0)) if res_total else 0

    print(f"Iniciando extracao de {total_no_ixc} clientes ativos...")
    pbar = tqdm(total=total_no_ixc, desc="Extraindo da API", unit="cli")

    while True:
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        payload_clientes = {
            "qtype": "ativo", "query": "S", "oper": "=",
            "page": str(pagina_atual), "rp": str(registros_por_pagina),
            "sortname": "id", "sortorder": "asc"
        }

        resposta = consultar_ixc("cliente", payload_clientes)
        if not resposta or 'registros' not in resposta:
            break
        clientes = resposta['registros']
        if not clientes:
            break

        for cliente in clientes:
            id_cli = cliente['id']
            res_logins = consultar_ixc("radusuarios", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "5000"})
            logins_encontrados = res_logins.get('registros', []) if res_logins else []

            if len(logins_encontrados) > 0:
                res_con = consultar_ixc("cliente_contrato", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "5000"})
                contratos_brutos = res_con.get('registros', []) if res_con else []

                base_de_dados_local.append({
                    "id_ixc": id_cli,
                    "nome_com_id": f"{id_cli} - {cliente['razao']}",
                    "fantasia": cliente.get('fantasia') or '',
                    "cpf_cnpj": cliente.get('cnpj_cpf') or '',
                    "contratos": _normalizar_contratos(contratos_brutos),
                    "logins": [_normalizar_login(l) for l in logins_encontrados],
                })
            pbar.update(1)
        pagina_atual += 1

    pbar.close()
    return base_de_dados_local


def extrair_clientes_recentes(historico, dias_retroativos=0):
    """Carga incremental: busca somente clientes/logins alterados recentemente."""
    from datetime import datetime, timedelta

    data_limite = (datetime.now() - timedelta(days=dias_retroativos)).strftime('%Y-%m-%d 00:00:00')
    ids_para_processar = set()

    print(f"Buscando novidades desde {data_limite}...")

    payload_cli = {
        "qtype": "data_atualizacao", "query": data_limite, "oper": ">=",
        "rp": "200", "sortname": "data_atualizacao", "sortorder": "desc"
    }
    res_cli = consultar_ixc("cliente", payload_cli)
    if res_cli and 'registros' in res_cli:
        for c in res_cli['registros']:
            ids_para_processar.add(str(c['id']))

    payload_logins = {
        "qtype": "id", "query": "0", "oper": ">",
        "rp": "100", "sortname": "id", "sortorder": "desc"
    }
    res_logins_recentes = consultar_ixc("radusuarios", payload_logins)
    if res_logins_recentes and 'registros' in res_logins_recentes:
        for l in res_logins_recentes['registros']:
            ids_para_processar.add(str(l['id_cliente']))

    if not ids_para_processar:
        print("Nada de novo encontrado no IXC.")
        return []

    print(f"Sincronizando detalhes de {len(ids_para_processar)} clientes...")

    base_de_dados_local = []
    pbar = tqdm(total=len(ids_para_processar), desc="Processando IXC", unit="cli")

    for id_cli in ids_para_processar:
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        cliente = consultar_ixc(f"cliente/{id_cli}", {})
        if not cliente or 'id' not in cliente:
            pbar.update(1)
            continue

        res_logins = consultar_ixc("radusuarios", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
        logins_brutos = res_logins.get('registros', []) if res_logins else []

        res_con = consultar_ixc("cliente_contrato", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
        contratos_brutos = res_con.get('registros', []) if res_con else []

        base_de_dados_local.append({
            "id_ixc": id_cli,
            "nome_com_id": f"{id_cli} - {cliente['razao']}",
            "fantasia": cliente.get('fantasia') or '',
            "cpf_cnpj": cliente.get('cnpj_cpf') or '',
            "contratos": _normalizar_contratos(contratos_brutos),
            "logins": [_normalizar_login(l) for l in logins_brutos],
        })
        pbar.update(1)

    pbar.close()
    return base_de_dados_local


def salvar_clientes_no_django(dados_ixc, mapa_filiais, mapa_cidades, historico, mapa_estados=None):
    """Grava clientes/enderecos extraidos do IXC, registrando alteracoes em
    LogAlteracaoIXC. Compartilhada pela carga total e pela incremental."""
    if not dados_ixc:
        return

    print("\nGravando e auditando alteracoes no banco...")
    pbar_save = tqdm(total=len(dados_ixc), desc="Gravando no Banco", unit="cli")

    for dado in dados_ixc:
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Parada solicitada via Admin")

        id_ixc = dado['id_ixc']
        cnpj_novo = str(dado.get('cpf_cnpj') or '').strip()
        razao_nova = dado['nome_com_id']

        cliente_obj = Cliente.objects.filter(id_ixc=id_ixc).first()
        if cliente_obj:
            if cliente_obj.cnpj_cpf != cnpj_novo:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="cnpj_cpf", valor_antigo=cliente_obj.cnpj_cpf, valor_novo=cnpj_novo)
            if cliente_obj.razao_social != razao_nova:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="razao_social", valor_antigo=cliente_obj.razao_social, valor_novo=razao_nova)

        cliente_obj, _ = Cliente.objects.update_or_create(
            id_ixc=id_ixc,
            defaults={
                'cnpj_cpf': cnpj_novo,
                'razao_social': razao_nova,
                'nome_fantasia': dado['fantasia'],
            }
        )

        for lg in dado.get('logins', []):
            login_nome = lg['login']
            circuit_id_novo = lg['circuit_id']
            con_pai = next((c for c in dado['contratos'] if str(c['id_contrato']) == str(lg['id_contrato'])), {})
            campos_tecnicos = extrair_campos_tecnicos_obs(lg.get('obs'))
            endereco_resolvido = resolver_endereco_login(
                lg,
                con_pai,
                mapa_cidades,
                mapa_estados=mapa_estados,
            )

            status_login_ixc = str(lg.get('ativo', 'S')).strip().upper()
            status_contrato_ixc = str(con_pai.get('status', 'A')).strip().upper()

            if status_contrato_ixc in ['C', 'D', 'CM', 'CANCELADO']:
                status_django = 'cancelado'
            elif status_login_ixc == 'N':
                status_django = 'inativo'
            else:
                status_django = 'ativo'

            filial_nova = mapa_filiais.get(con_pai.get('filial_id'), f"Filial {con_pai.get('filial_id')}")

            end_atual = Endereco.objects.filter(cliente=cliente_obj, login_ixc=login_nome).first()
            if end_atual:
                if end_atual.status != status_django:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="status", valor_antigo=end_atual.status, valor_novo=status_django)
                if end_atual.filial_ixc != filial_nova:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="filial", valor_antigo=end_atual.filial_ixc, valor_novo=filial_nova)
                if str(end_atual.agent_circuit_id or '').strip() != circuit_id_novo:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="agent_circuit_id", valor_antigo=end_atual.agent_circuit_id, valor_novo=circuit_id_novo)

            Endereco.objects.update_or_create(
                cliente=cliente_obj,
                login_ixc=login_nome,
                defaults={
                    'cep': endereco_resolvido['cep'],
                    'logradouro': endereco_resolvido['logradouro'],
                    'numero': endereco_resolvido['numero'],
                    'bairro': endereco_resolvido['bairro'],
                    'cidade': endereco_resolvido['cidade'],
                    'cidade_id_ixc': endereco_resolvido['cidade_id_ixc'],
                    'estado': endereco_resolvido['estado'],
                    'login_id_ixc': str(lg.get('id_login') or '').strip() or None,
                    'contrato_id_ixc': str(lg.get('id_contrato') or '').strip() or None,
                    'filial_ixc': filial_nova,
                    'agent_circuit_id': circuit_id_novo,
                    'status': status_django,
                    'velocidade': campos_tecnicos.get('velocidade') or None,
                    'tipo_acesso': campos_tecnicos.get('tipo_acesso') or None,
                    'ipv4_bloco': campos_tecnicos.get('ipv4_bloco') or None,
                    'dupla_abordagem': campos_tecnicos.get('dupla_abordagem') or None,
                    'entrega_rb': campos_tecnicos.get('entrega_rb') or None,
                }
            )
        pbar_save.update(1)

    pbar_save.close()
