# Status Atual

## Resumo executivo

O projeto apresenta uma base funcional relevante e ja separada em dominios, mas ainda com sinais de crescimento organico sem consolidacao documental e sem fronteira clara entre:

- navegacao web interna;
- servicos de apoio;
- integracoes;
- API externa.

## Leitura atual da estrutura

Os modulos identificados hoje sao:

- `core`
- `leads`
- `partners`
- `clientes`
- `auditoria`
- `core_admin`
- `backoffice`

## Diagnostico funcional

### Pontos positivos

- existe separacao inicial por dominio;
- existem rotas e modelos concentrados por area funcional;
- ha trilha de auditoria e rotinas de integracao ja relevantes para o negocio;
- o sistema ja possui `djangorestframework` instalado, o que reduz esforco de fundacao para API.

### Pontos de atencao

- nao existe pasta `docs/` estruturada;
- as rotas internas e os endpoints JSON convivem sem fronteira publica clara;
- ha reuse do mesmo modulo em multiplos prefixes de URL;
- views extensas indicam concentracao excessiva de responsabilidades;
- integracoes estao dispersas entre scripts, views administrativas e auditoria;
- nao existe Swagger/OpenAPI ativo.

## Decisao registrada

O produto vai seguir com a `Opcao B`:

- nova camada dedicada para API e integracoes;
- preservacao dos modulos de negocio atuais;
- abertura incremental de contratos externos em `/api/v1/`.

## Principais riscos

- publicar contratos externos em cima de rotas internas atuais pode gerar retrabalho;
- sem definicao de modulo dono da API, a manutencao tende a continuar difusa;
- sem backlog priorizado, a equipe pode atacar temas tecnicos sem ordem de valor.

## Proximo estado desejado

- documentacao-base criada e adotada;
- backlog com prioridade e criterios de aceite;
- sprint inicial de backend organizada;
- modulo dedicado de API/integracoes definido;
- primeira versao do Swagger publicada em ambiente controlado.
