from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models


class ProcessoRedeBase(models.Model):
    """Campos comuns a RedeExterna/RedeInterna (ADR-012).

    `setor`/`status` sao FK para o catalogo `Setor`/`SetorStatus`
    (ADR-014/ADR-015) — `setor` deve pertencer ao `processo` vinculado, e
    `status` deve pertencer ao `setor` vinculado (validado em `clean()`).
    Nao ha sincronizacao com os campos `setor_re`/`setor_ri`/
    `parceiro_re`/`parceiro_ri` ja existentes em `Escola.dados_api` — a
    criacao do processo comeca em branco.

    `responsavel` (RN-052/ADR-027): usuario do sistema atribuido/
    reatribuivel manualmente pela tela — nunca preenchido automaticamente
    com "quem criou". Mesmo padrao de nulidade de `setor`/`status`/
    `parceiro` (obrigatoriedade e so via camada de negocio/UI, RN-026).
    `related_name` usa `%(class)s` para nao colidir entre RedeExterna/
    RedeInterna/MapaCalor apontando para o mesmo `core.User`.
    """

    setor = models.ForeignKey(
        "Setor", verbose_name="Setor", null=True, blank=True, on_delete=models.SET_NULL,
    )
    status = models.ForeignKey(
        "SetorStatus", verbose_name="Status", null=True, blank=True, on_delete=models.SET_NULL,
    )
    parceiro = models.ForeignKey(
        "partners.Partner",
        verbose_name="Parceiro",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Responsavel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="%(class)s_responsavel",
    )
    dados_adicionais = models.JSONField("Dados adicionais", default=dict, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.setor_id and self.processo_id and self.setor.processo_id != self.processo_id:
            raise ValidationError({"setor": "O setor precisa pertencer ao processo escolhido."})
        if self.status_id and self.setor_id and self.status.setor_id != self.setor_id:
            raise ValidationError({"status": "O status precisa pertencer ao setor escolhido."})


class Escola(models.Model):
    """Escola sincronizada do DashboardEACE (ADR-010).

    `dados_api` guarda o payload bruto completo retornado por `GET
    /escolas/{jira_key}` — fonte de verdade enquanto o schema completo de
    `EscolaOut` nao e confirmado. Campos relevantes podem ser promovidos a
    colunas tipadas proprias depois, sem exigir nova ADR.
    """

    jira_key = models.CharField("Chave Jira", max_length=32, unique=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    status_escola = models.CharField("Status da Escola", max_length=60, blank=True)
    inep = models.CharField("Codigo INEP", max_length=20, blank=True)
    nome = models.CharField("Nome da Escola", max_length=255, blank=True)
    municipio = models.CharField("Municipio", max_length=120, blank=True)
    endereco_descricao = models.TextField("Endereco", blank=True)
    logradouro = models.CharField("Logradouro", max_length=255, blank=True)
    numero = models.CharField("Numero", max_length=20, blank=True)
    bairro = models.CharField("Bairro", max_length=120, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)
    velocidade_dl_minima = models.DecimalField(
        "Velocidade Minima",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="RN-057 Parte 1: promovido de dados_api.velocidade_dl_minima (DashboardEACE).",
    )
    kit_inicial = models.DecimalField(
        "Kit Inicial",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "RN-057 Parte 2: promovido de dados_api.kit_wifi (DashboardEACE). "
            "Nome de exibicao ainda nao confirmado literalmente com o time EACE."
        ),
    )
    dados_api = models.JSONField("Dados da API", default=dict, blank=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Escola"
        verbose_name_plural = "Escolas"
        ordering = ["jira_key"]

    def __str__(self):
        return self.jira_key

    @staticmethod
    def _formatar_velocidade(valor):
        if valor in (None, ""):
            return ""
        try:
            return f"{float(valor):g} Mbps"
        except (TypeError, ValueError):
            return f"{valor} Mbps"

    @staticmethod
    def _formatar_numero(valor):
        """Mesmo espirito de `_formatar_velocidade` (sem sufixo de unidade
        inventado), usado por campos cuja unidade nao esta confirmada
        (Kit Inicial, TARGET EACE — RN-057). Usa `Decimal` (nao `float`/`:g`)
        para nao perder precisao nem cair em notacao cientifica em valores
        maiores (`max_digits=10`)."""
        if valor in (None, ""):
            return ""
        try:
            decimal_valor = Decimal(valor).normalize()
        except (InvalidOperation, TypeError, ValueError):
            return str(valor)
        return format(decimal_valor, "f")

    @property
    def target_eace(self):
        """RN-057 Parte 3/ADR-029: TARGET EACE nao e armazenado por Escola —
        e sempre derivado por lookup (UF + Velocidade Minima da Escola)
        contra o catalogo `TargetRedeExterna`. Sem correspondencia exata,
        devolve None (nunca aproximado)."""
        return TargetRedeExterna.buscar_valor(self.uf, self.velocidade_dl_minima)

    @property
    def dados_tecnicos_eace(self):
        """RN-057: os tres dados tecnicos EACE (Velocidade Minima, Kit
        Inicial, TARGET EACE) desta Escola, sempre somente leitura, exibidos
        na area de Campos vinculada a Atividade Principal (RN-037/038—
        RN-038 nao se aplica: os valores variam por Escola, nao sao fixos)."""
        return {
            "velocidade_minima": self._formatar_velocidade(self.velocidade_dl_minima),
            "kit_inicial": self._formatar_numero(self.kit_inicial),
            "target_eace": self._formatar_numero(self.target_eace),
        }

    def _referencia_rede(self, sufixo):
        """Referencia somente-leitura de RE/RI que ja vem da API do
        DashboardEACE, direto de `dados_api` (ADR-013). Nao tem relacao com
        os processos internos `RedeExterna`/`RedeInterna` (ADR-012).
        `velocidade_dl_ofertada` e um dado da escola (nao existe separado
        por RE/RI na API), repetido nos dois para exibicao."""
        dados = self.dados_api or {}
        return {
            "setor": dados.get(f"setor_{sufixo}") or "",
            "parceiro": dados.get(f"parceiro_{sufixo}") or "",
            "velocidade_ofertada": self._formatar_velocidade(dados.get("velocidade_dl_ofertada")),
        }

    @property
    def referencia_rede_externa(self):
        return self._referencia_rede("re")

    @property
    def referencia_rede_interna(self):
        return self._referencia_rede("ri")

    @property
    def referencia_mapa_calor(self):
        """RN-043 (excecao): Mapa Calor nao tem, ate o momento, nenhum dado
        de referencia somente-leitura equivalente ao `dados_api.setor_re`/
        `parceiro_re` (RN-024) vindo da API do DashboardEACE — devolve
        sempre vazio, no mesmo formato usado pelo template
        (`referencia.parceiro`/`referencia.velocidade_ofertada`)."""
        return {"setor": "", "parceiro": "", "velocidade_ofertada": ""}

    @property
    def indicador_conectividade(self):
        """RN-062: bolinha do grid de Enderecos Lastmile, derivada somente
        da conclusao de RedeExterna (RE) e RedeInterna (RI) — Mapa Calor
        nunca entra nesse calculo. "Concluida" e comparacao exata do nome
        do Status (decisao do usuario; RN-025 mantem o catalogo como texto
        livre por Setor, sem novo campo booleano). Texto comparado e
        "Concluido" sem acento — mesma grafia usada em 100% do catalogo
        real e nas migrations de seed do projeto (bug corrigido, RN-062).
        RE/RI sem registro para a Escola contam como nao concluida (mesmo
        acesso seguro via `getattr` ja usado em `apps/leads/views.py`)."""
        def _concluida(rede):
            status = getattr(rede, "status", None)
            return bool(status and status.nome == "Concluido")

        re_concluida = _concluida(getattr(self, "rede_externa", None))
        ri_concluida = _concluida(getattr(self, "rede_interna", None))

        if re_concluida and ri_concluida:
            return {"cor": "verde", "rotulo": "Conectada"}
        if re_concluida or ri_concluida:
            return {"cor": "amarelo", "rotulo": "Parcialmente conectada"}
        return {"cor": "vermelho", "rotulo": "Desconectada"}


class RedeExterna(ProcessoRedeBase):
    """Processo de Rede Externa (RE) da escola (ADR-012, RN-023).

    `NOME_PROCESSO_PADRAO` identifica qual `Processo` (cadastrado na tela
    de Processos, PO-050) e usado por todo RE — configurado uma vez, o
    usuario nao escolhe o Processo linha a linha no grid (ADR-015)."""

    NOME_PROCESSO_PADRAO = "Rede Externa (RE)"

    escola = models.OneToOneField(
        Escola, on_delete=models.CASCADE, related_name="rede_externa"
    )
    processo = models.ForeignKey(
        "Processo",
        verbose_name="Processo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="redes_externas",
    )

    class Meta:
        verbose_name = "Rede Externa"
        verbose_name_plural = "Redes Externas"

    def __str__(self):
        return f"RE - {self.escola.jira_key}"


class RedeInterna(ProcessoRedeBase):
    """Processo de Rede Interna (RI) da escola (ADR-012, RN-023).

    `NOME_PROCESSO_PADRAO` identifica qual `Processo` (cadastrado na tela
    de Processos, PO-050) e usado por todo RI — configurado uma vez, o
    usuario nao escolhe o Processo linha a linha no grid (ADR-015)."""

    NOME_PROCESSO_PADRAO = "Rede Interna (RI)"

    escola = models.OneToOneField(
        Escola, on_delete=models.CASCADE, related_name="rede_interna"
    )
    processo = models.ForeignKey(
        "Processo",
        verbose_name="Processo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="redes_internas",
    )

    class Meta:
        verbose_name = "Rede Interna"
        verbose_name_plural = "Redes Internas"

    def __str__(self):
        return f"RI - {self.escola.jira_key}"


class MapaCalor(ProcessoRedeBase):
    """Processo de Mapa Calor (MC) da escola (RN-043, PO-067): terceira
    subatividade fixa, no mesmo molde hardcoded de `RedeExterna`/
    `RedeInterna` (ADR-012) — decisao de adiar a generalizacao registrada
    em ADR-025.

    `NOME_PROCESSO_PADRAO` identifica qual `Processo` (cadastrado na tela
    de Processos, PO-050) e usado por todo Mapa Calor — configurado uma
    vez, o usuario nao escolhe o Processo linha a linha no grid (ADR-015),
    mesmo padrao de RE/RI."""

    NOME_PROCESSO_PADRAO = "Mapa Calor (MC)"

    escola = models.OneToOneField(
        Escola, on_delete=models.CASCADE, related_name="mapa_calor"
    )
    processo = models.ForeignKey(
        "Processo",
        verbose_name="Processo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mapas_calor",
    )

    class Meta:
        verbose_name = "Mapa Calor"
        verbose_name_plural = "Mapas Calor"

    def __str__(self):
        return f"MC - {self.escola.jira_key}"


class TargetRedeExterna(models.Model):
    """Catalogo de referencia do TARGET EACE por UF + Velocidade (RN-057
    Parte 3, ADR-029) — espelha por completo a tabela `target_rede_externa`
    do banco de origem do DashboardEACE (`eace_jira`). Sem FK com `Escola`:
    o TARGET EACE de uma Escola e sempre um lookup (uf + velocidade_mbps),
    nunca um valor gravado na linha da Escola (ver `Escola.target_eace`).

    `velocidade_mbps` e `int` (match exato, mesma chave unica da origem) —
    o cruzamento com `Escola.velocidade_dl_minima` (`Decimal`) e feito em
    `buscar_valor`, que so casa quando a velocidade da Escola for um valor
    inteiro exato (nunca aproximado, RN-057)."""

    uf = models.CharField("UF", max_length=2)
    velocidade_mbps = models.PositiveIntegerField("Velocidade (Mbps)")
    valor = models.DecimalField("Valor", max_digits=10, decimal_places=2)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Target Rede Externa"
        verbose_name_plural = "Targets Rede Externa"
        ordering = ["uf", "velocidade_mbps"]
        constraints = [
            models.UniqueConstraint(
                fields=["uf", "velocidade_mbps"], name="target_rede_externa_unico_uf_velocidade",
            ),
        ]

    def __str__(self):
        return f"{self.uf} - {self.velocidade_mbps} Mbps: {self.valor}"

    @classmethod
    def buscar_valor(cls, uf, velocidade):
        """Lookup exato (uf + velocidade) — ADR-029: sem correspondencia
        exata, devolve None (nunca aproximado). `velocidade` normalmente e
        `Escola.velocidade_dl_minima` (Decimal); so casa quando representar
        um numero inteiro exato, ja que a origem (`velocidade_mbps`) e
        `int`."""
        if not uf or velocidade in (None, ""):
            return None
        try:
            velocidade_decimal = Decimal(velocidade)
        except (InvalidOperation, TypeError, ValueError):
            return None
        if velocidade_decimal != velocidade_decimal.to_integral_value():
            return None
        alvo = cls.objects.filter(uf=uf, velocidade_mbps=int(velocidade_decimal)).first()
        return alvo.valor if alvo else None


class Processo(models.Model):
    """Catalogo de processos vinculaveis a RedeExterna/RedeInterna
    (ADR-014, RN-025). Generico por design: nao tem campo `tipo` — a
    distincao entre RE e RI vem de qual model aponta para ele."""

    nome = models.CharField("Nome", max_length=120, unique=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Processo"
        verbose_name_plural = "Processos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Setor(models.Model):
    """Setor que compoe um Processo (ADR-014, RN-025)."""

    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="setores")
    nome = models.CharField("Nome", max_length=120)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        ordering = ["processo__nome", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["processo", "nome"], name="setor_unico_por_processo"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.processo.nome})"


class SetorStatus(models.Model):
    """Status que compoe um Setor (ADR-014, RN-025)."""

    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name="status_opcoes")
    nome = models.CharField("Nome", max_length=120)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Status do Setor"
        verbose_name_plural = "Status dos Setores"
        ordering = ["setor__processo__nome", "setor__nome", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["setor", "nome"], name="status_unico_por_setor"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.setor})"


class Campo(models.Model):
    """Campo personalizado por Setor, exibido no modal de RE/RI (RN-032)
    e cadastrado pela tela "Campos" da Administracao (ADR-019, RN-031).

    `setor_nome` e texto (mesmo vocabulario de `Setor.nome`), nao FK para
    uma linha especifica de Setor de um Processo — assim o mesmo campo
    vale tanto para RE quanto para RI (ver ADR-019, decisao detalhada).

    RN-039/ADR-024 acrescentou duas capacidades aditivas, sem mudar o
    comportamento de Campo ja cadastrado:
    - `status_condicionante_nome`: quando preenchido, o Campo so aparece no
      modal (RN-032) enquanto o Status atual do RE/RI exibido tiver esse
      mesmo nome (mesmo vocabulario de `SetorStatus.nome`, RN-025);
    - tipo `TIPO_CALCULADO`: valor nunca digitado nem gravado em
      `CampoValor` — derivado ao vivo somando `horas_prazo` (convertidas em
      dias corridos, arredondado para cima) ao valor atual do `campo_base`
      (outro Campo do mesmo `setor_nome`, obrigatoriamente tipo Data)."""

    TIPO_TEXTO = "texto"
    TIPO_NUMERO = "numero"
    TIPO_DATA = "data"
    TIPO_SIM_NAO = "sim_nao"
    TIPO_LISTA = "lista"
    TIPO_CALCULADO = "calculado"
    TIPO_CHOICES = [
        (TIPO_TEXTO, "Texto curto"),
        (TIPO_NUMERO, "Número"),
        (TIPO_DATA, "Data"),
        (TIPO_SIM_NAO, "Sim/Não"),
        (TIPO_LISTA, "Lista"),
        (TIPO_CALCULADO, "Calculado"),
    ]

    nome = models.CharField("Nome", max_length=120)
    tipo = models.CharField("Tipo", max_length=20, choices=TIPO_CHOICES)
    setor_nome = models.CharField("Setor dono", max_length=120)
    opcoes = models.JSONField("Opções", default=list, blank=True)
    status_condicionante_nome = models.CharField(
        "Status condicionante", max_length=120, blank=True, default="",
    )
    campo_base = models.ForeignKey(
        "self",
        verbose_name="Campo base",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="campos_calculados",
        # PROTECT (pendencia da ADR-024 resolvida aqui): um Campo usado como
        # base de algum Campo calculado nao pode ser excluido — evita que o
        # valor calculado suma silenciosamente. Quem excluir precisa antes
        # remover ou reapontar o(s) Campo(s) calculado(s) dependentes.
    )
    horas_prazo = models.PositiveIntegerField("Horas de prazo", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Campo"
        verbose_name_plural = "Campos"
        ordering = ["setor_nome", "nome"]

    def clean(self):
        super().clean()
        if self.tipo == self.TIPO_LISTA and not self.opcoes:
            # Erro sem campo associado (nao "opcoes"): Model.clean() roda mesmo
            # quando o campo esta fora do form (ex.: CampoForm usa "opcoes_texto"),
            # e o ModelForm nao consegue mapear um erro de campo ausente do form.
            raise ValidationError("Informe pelo menos uma opção para o tipo Lista.")

        if self.tipo == self.TIPO_CALCULADO:
            if not self.campo_base_id:
                raise ValidationError("Informe o Campo base para o tipo Calculado.")
            if self.pk and self.campo_base_id == self.pk:
                raise ValidationError("O Campo base não pode ser o próprio campo.")
            if self.campo_base.tipo != self.TIPO_DATA:
                raise ValidationError("O Campo base do tipo Calculado precisa ser do tipo Data.")
            if self.campo_base.setor_nome != self.setor_nome:
                raise ValidationError("O Campo base precisa pertencer ao mesmo Setor do Campo calculado.")
            if not self.horas_prazo or self.horas_prazo <= 0:
                raise ValidationError("Informe um número positivo de horas de prazo para o tipo Calculado.")

    def __str__(self):
        return f"{self.nome} ({self.setor_nome})"


class CampoObrigatoriedadeTransicao(models.Model):
    """RN-061/ADR-031: regra de obrigatoriedade de um Campo (RN-031) ao
    trocar de Setor. O Setor de origem da regra e sempre `campo.setor_nome`
    (mesmo Setor dono que ja e o unico a editar o Campo, RN-032) — nao um
    campo proprio, para nao divergir do dono real do Campo. Um mesmo Campo
    pode ter varias regras, uma por Setor de destino (`setor_destino_nome`,
    mesmo vocabulario de `Setor.nome`, RN-025). Enquanto o RE/RI/MapaCalor
    (RN-023/RN-043) dono do valor estiver trocando do Setor dono do Campo
    para `setor_destino_nome`, o `CampoValor` desse Campo precisa estar
    preenchido, ou a troca e bloqueada (RN-061)."""

    campo = models.ForeignKey(
        Campo, verbose_name="Campo", on_delete=models.CASCADE, related_name="regras_obrigatoriedade",
    )
    setor_destino_nome = models.CharField("Setor de destino", max_length=120)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        verbose_name = "Obrigatoriedade de Campo por transição"
        verbose_name_plural = "Obrigatoriedades de Campo por transição"
        ordering = ["campo__setor_nome", "campo__nome", "setor_destino_nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["campo", "setor_destino_nome"], name="regra_obrigatoriedade_unica_por_campo_e_destino",
            ),
        ]

    def clean(self):
        super().clean()
        if self.campo_id and self.campo.tipo == Campo.TIPO_CALCULADO:
            raise ValidationError(
                "Um Campo do tipo Calculado não pode ter regra de obrigatoriedade — nunca é preenchido manualmente."
            )
        if self.campo_id and self.setor_destino_nome == self.campo.setor_nome:
            raise ValidationError("O Setor de destino não pode ser igual ao Setor dono do Campo.")

    def __str__(self):
        return f"{self.campo.nome}: obrigatório para {self.setor_destino_nome}"


class SetorEscopo(models.Model):
    """Escopo de exibicao do Setor (RN-025) entre Escola e RE/RI/Mapa Calor
    (RN-037/RN-043).

    Definido por nome de Setor (mesmo vocabulario de `Setor.nome`), nao por
    uma linha especifica de Setor de um Processo — mesmo precedente ja
    usado por `Campo.setor_nome` (ADR-019), para nao divergir entre RE, RI
    e Mapa Calor. Setor sem registro aqui mantem o comportamento legado
    (Sub-atividades: RE, RI e Mapa Calor) — ver migracao de dados desta
    feature (ADR-022). `aplica_mapa_calor` (RN-043/PO-067) segue o mesmo
    padrao de `aplica_re`/`aplica_ri`, com default `True` para nao mudar o
    comportamento de escopo ja configurado antes desta feature."""

    ATIVIDADE_ESCOLA = "escola"
    ATIVIDADE_SUB_ATIVIDADES = "sub_atividades"
    ATIVIDADE_CHOICES = [
        (ATIVIDADE_ESCOLA, "Atividade principal (Escola)"),
        (ATIVIDADE_SUB_ATIVIDADES, "Sub-atividades (RE/RI/MC)"),
    ]

    setor_nome = models.CharField("Setor", max_length=120, unique=True)
    atividade = models.CharField("Onde aparece", max_length=20, choices=ATIVIDADE_CHOICES)
    aplica_re = models.BooleanField("Rede Externa (RE)", default=True)
    aplica_ri = models.BooleanField("Rede Interna (RI)", default=True)
    aplica_mapa_calor = models.BooleanField("Mapa Calor (MC)", default=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Escopo do Setor"
        verbose_name_plural = "Escopos dos Setores"
        ordering = ["setor_nome"]

    def clean(self):
        super().clean()
        if self.atividade == self.ATIVIDADE_SUB_ATIVIDADES and not (self.aplica_re or self.aplica_ri or self.aplica_mapa_calor):
            raise ValidationError("Selecione ao menos RE, RI ou Mapa Calor quando o escopo for Sub-atividades.")

    @property
    def rotulo_sub_atividades(self):
        """RN-043: rotulo textual das sub-atividades marcadas (RE/RI/MC),
        reaproveitado tanto por `__str__` quanto pela tela de Administracao
        (`core_admin/setor_escopo_list.html`)."""
        partes = [
            nome for nome, ativo in (
                ("RE", self.aplica_re), ("RI", self.aplica_ri), ("MC", self.aplica_mapa_calor),
            ) if ativo
        ]
        return ' e '.join(partes) or 'Sub-atividades'

    def __str__(self):
        if self.atividade == self.ATIVIDADE_ESCOLA:
            return f"{self.setor_nome}: Escola"
        return f"{self.setor_nome}: {self.rotulo_sub_atividades}"


class CampoValor(models.Model):
    """Valor de um Campo (RN-031) para uma instancia especifica de
    RedeExterna/RedeInterna (RN-023) ou de Escola, conforme o escopo do
    Setor dono do campo (`SetorEscopo`, RN-037). GenericForeignKey — mesmo
    padrao ja usado por `RegistroHistorico` (apps.core.models) — evita
    duplicar o model de valor por alvo (ADR-019/ADR-022)."""

    campo = models.ForeignKey(Campo, verbose_name="Campo", on_delete=models.CASCADE, related_name="valores")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    valor = models.JSONField("Valor", null=True, blank=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Valor de Campo"
        verbose_name_plural = "Valores de Campo"
        constraints = [
            models.UniqueConstraint(
                fields=["campo", "content_type", "object_id"],
                name="valor_unico_por_campo_e_instancia",
            ),
        ]

    def __str__(self):
        return f"{self.campo.nome}: {self.valor!r}"


class CotacaoParceiro(models.Model):
    """RN-044/ADR-026: Parceiro candidato em cotacao para um RedeExterna ou
    RedeInterna especifico, enquanto esse RE/RI estiver no Status "Cotacao"
    (SetorStatus do Setor "Lastmile", RN-025). `GenericForeignKey` — mesmo
    padrao ja usado por `CampoValor`/`RegistroHistorico` (apps.core.models)
    — evita uma FK de `apps.partners` para `apps.escolas`, que inverteria a
    direcao de dependencia aprovada (ADR-007 item 7). Escopo limitado a
    RE/RI (Mapa Calor fora, ver ADR-026).

    Regra de vencedor unico: no maximo uma linha com `situacao="selecionado"`
    por `(content_type, object_id)` — reforcada no banco (`UniqueConstraint`
    condicional) e na camada de servico (`apps/leads/services.py::
    selecionar_candidato_cotacao`, que move os demais candidatos do mesmo
    RE/RI para "recusado" na mesma operacao)."""

    SITUACAO_EM_COTACAO = "em_cotacao"
    SITUACAO_SELECIONADO = "selecionado"
    SITUACAO_RECUSADO = "recusado"
    SITUACAO_CHOICES = [
        (SITUACAO_EM_COTACAO, "Em cotação"),
        (SITUACAO_SELECIONADO, "Selecionado"),
        (SITUACAO_RECUSADO, "Recusado"),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    parceiro = models.ForeignKey(
        "partners.Partner",
        verbose_name="Parceiro",
        on_delete=models.CASCADE,
        related_name="cotacoes_rede",
    )
    situacao = models.CharField(
        "Situação", max_length=20, choices=SITUACAO_CHOICES, default=SITUACAO_EM_COTACAO,
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Cotação de Parceiro"
        verbose_name_plural = "Cotações de Parceiros"
        ordering = ["-criado_em"]
        constraints = [
            # Decisao tecnica de baixo risco do Dev (nao pedida pela ADR-026
            # nem pela RN-044): impede duplicar o mesmo Parceiro como
            # candidato do mesmo RE/RI.
            models.UniqueConstraint(
                fields=["content_type", "object_id", "parceiro"],
                name="cotacaoparceiro_parceiro_unico_por_instancia",
            ),
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                condition=models.Q(situacao="selecionado"),
                name="cotacaoparceiro_um_selecionado_por_instancia",
            ),
        ]

    def __str__(self):
        return f"{self.parceiro} ({self.get_situacao_display()})"
