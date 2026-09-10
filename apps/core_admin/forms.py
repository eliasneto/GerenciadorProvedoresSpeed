from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.escolas.models import Campo, CampoObrigatoriedadeTransicao, Processo, Setor, SetorEscopo, SetorStatus
from apps.leads.models import AcessoSetor

User = get_user_model()

# PO-077/RN-058/ADR-030: os 6 grupos/modulos do menu principal hoje
# existentes (`ops/setup_speed.py`), com o rotulo exibido em `core/base.html`.
GRUPOS_MODULO = [
    ('LastMile', 'Projeto'),
    ('Setor', 'Setores'),
    ('Parceiro', 'Parceiros'),
    ('Backoffice', 'Backoffice'),
    ('Gestao', 'Gestão'),
    ('Administrador', 'Administrador'),
]


class AcessoForm(forms.Form):
    """PO-077/RN-058/RN-059/ADR-030: concede/revoga, para um usuario
    selecionado, pertencimento aos 6 grupos/modulos do menu e Setores
    individuais (`AcessoSetor`, RN-055), em um formulario so."""

    usuario_id = forms.IntegerField(widget=forms.HiddenInput)
    grupos = forms.MultipleChoiceField(choices=GRUPOS_MODULO, required=False)
    confirmar_revogar_administrador = forms.BooleanField(
        required=False,
        label="Confirmo a revogação do módulo Administrador",
    )
    setores = forms.MultipleChoiceField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nomes_setor = list(dict.fromkeys(
            Setor.objects.order_by('nome').values_list('nome', flat=True)
        ))
        self.fields['setores'].choices = [(nome, nome) for nome in nomes_setor]

    def clean_usuario_id(self):
        usuario_id = self.cleaned_data['usuario_id']
        if not User.objects.filter(pk=usuario_id).exists():
            raise forms.ValidationError("Usuario nao encontrado.")
        return usuario_id

    def clean(self):
        cleaned_data = super().clean()
        usuario_id = cleaned_data.get('usuario_id')
        grupos = cleaned_data.get('grupos') or []

        # RN-058: revogar o modulo Administrador de qualquer usuario
        # (inclusive o proprio usuario logado) exige confirmacao explicita.
        if usuario_id and 'Administrador' not in grupos:
            tinha_administrador = User.objects.filter(
                pk=usuario_id, groups__name='Administrador'
            ).exists()
            if tinha_administrador and not cleaned_data.get('confirmar_revogar_administrador'):
                raise forms.ValidationError(
                    "Confirme a revogação do módulo Administrador antes de salvar "
                    "(marque a caixa de confirmação abaixo)."
                )
        return cleaned_data

    def save(self):
        """Aplica as concessoes/revogacoes de grupo (modulo) e de Setor
        individual (`AcessoSetor`). RN-059: conceder um Setor individual a
        usuario que ainda nao pertence ao grupo `Setor` o inclui nesse
        grupo automaticamente, na mesma acao."""
        usuario = User.objects.get(pk=self.cleaned_data['usuario_id'])
        grupos_selecionados = set(self.cleaned_data['grupos'])
        setores_selecionados = set(self.cleaned_data['setores'])

        setores_atuais = set(
            AcessoSetor.objects.filter(usuario=usuario).values_list('setor_nome', flat=True)
        )
        setores_novos = setores_selecionados - setores_atuais
        pertencia_ao_grupo_setor_antes = usuario.groups.filter(name='Setor').exists()

        for nome_grupo, _rotulo in GRUPOS_MODULO:
            grupo = Group.objects.get(name=nome_grupo)
            pertence = usuario.groups.filter(pk=grupo.pk).exists()
            deveria_pertencer = nome_grupo in grupos_selecionados
            if deveria_pertencer and not pertence:
                usuario.groups.add(grupo)
            elif not deveria_pertencer and pertence:
                usuario.groups.remove(grupo)

        for nome in setores_novos:
            AcessoSetor.objects.create(usuario=usuario, setor_nome=nome)
        AcessoSetor.objects.filter(
            usuario=usuario, setor_nome__in=setores_atuais - setores_selecionados
        ).delete()

        if setores_novos and not pertencia_ao_grupo_setor_antes:
            # RN-059: concessao de Setor individual inclui automaticamente
            # no grupo Setor, mesmo que o checkbox do modulo nao tenha sido
            # marcado nesta mesma submissao.
            usuario.groups.add(Group.objects.get(name='Setor'))

        return usuario


class ProcessoForm(forms.ModelForm):
    class Meta:
        model = Processo
        fields = ['nome']
        labels = {'nome': 'Nome do processo'}


class SetorForm(forms.ModelForm):
    class Meta:
        model = Setor
        fields = ['nome']
        labels = {'nome': 'Nome do setor'}


class SetorStatusForm(forms.ModelForm):
    class Meta:
        model = SetorStatus
        fields = ['nome']
        labels = {'nome': 'Nome do status'}


class SetorEscopoForm(forms.ModelForm):
    """PO-062/ADR-022: escopo de exibicao do Setor (RN-025) entre Escola e
    RE/RI/Mapa Calor (RN-037/RN-043). `setor_nome` usa o mesmo vocabulario
    ja cadastrado em `Setor.nome` (RN-025), mesmo padrao ja usado em
    `CampoForm` (RN-031)."""

    setor_nome = forms.ChoiceField(label="Setor")

    class Meta:
        model = SetorEscopo
        fields = ['setor_nome', 'atividade', 'aplica_re', 'aplica_ri', 'aplica_mapa_calor']
        labels = {
            'atividade': 'Onde aparece',
            'aplica_re': 'Rede Externa (RE)',
            'aplica_ri': 'Rede Interna (RI)',
            'aplica_mapa_calor': 'Mapa Calor (MC)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['aplica_re'].required = False
        self.fields['aplica_ri'].required = False
        self.fields['aplica_mapa_calor'].required = False

        nomes_setor = list(dict.fromkeys(Setor.objects.order_by('nome').values_list('nome', flat=True)))
        if self.instance.pk:
            # Editando: o nome do Setor nao muda mais depois de configurado
            # (para reatribuir o escopo a outro nome, cria-se um registro
            # novo para ele); a escolha some da lista de "criar" abaixo.
            self.fields['setor_nome'].disabled = True
        else:
            # Criando: Setor que ja tem escopo configurado sai da lista —
            # para reconfigurar um Setor ja configurado, usa "editar".
            ja_configurados = set(SetorEscopo.objects.values_list('setor_nome', flat=True))
            nomes_setor = [nome for nome in nomes_setor if nome not in ja_configurados]
        self.fields['setor_nome'].choices = [(nome, nome) for nome in nomes_setor]

    def clean(self):
        cleaned_data = super().clean()
        atividade = cleaned_data.get('atividade')
        if atividade == SetorEscopo.ATIVIDADE_SUB_ATIVIDADES and not (
            cleaned_data.get('aplica_re') or cleaned_data.get('aplica_ri') or cleaned_data.get('aplica_mapa_calor')
        ):
            self.add_error(None, "Selecione ao menos RE, RI ou Mapa Calor quando o escopo for Sub-atividades.")
        return cleaned_data


class CampoForm(forms.ModelForm):
    """PO-057/ADR-019: cadastro de Campos personalizados por Setor
    (RN-031). `setor_nome` usa o mesmo vocabulario ja cadastrado em
    `Setor.nome` (RN-025), oferecido como lista para evitar divergencia
    de digitacao entre RE e RI. PO-063/RN-039/ADR-024 acrescentou o Status
    condicionante (texto livre, mesmo vocabulario de `SetorStatus.nome`) e
    o tipo Calculado (exige Campo base do tipo Data, do mesmo Setor, e
    Horas de prazo positivas)."""

    setor_nome = forms.ChoiceField(label="Setor dono")
    opcoes_texto = forms.CharField(
        label="Opções (uma por linha, somente para o tipo Lista)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta:
        model = Campo
        fields = ['nome', 'tipo', 'setor_nome', 'status_condicionante_nome', 'campo_base', 'horas_prazo']
        labels = {
            'nome': 'Nome do campo',
            'tipo': 'Tipo',
            'status_condicionante_nome': 'Status condicionante',
            'campo_base': 'Campo base',
            'horas_prazo': 'Horas de prazo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nomes_setor = Setor.objects.order_by('nome').values_list('nome', flat=True)
        self.fields['setor_nome'].choices = [(nome, nome) for nome in dict.fromkeys(nomes_setor)]
        if self.instance.pk:
            # PO-061/RN-036: "opcoes" nao e campo do model form (usa
            # "opcoes_texto"), entao o initial padrao do ModelForm nao
            # preenche o textarea ao editar um Campo existente.
            self.fields['opcoes_texto'].initial = "\n".join(self.instance.opcoes)

        self.fields['status_condicionante_nome'].required = False
        self.fields['horas_prazo'].required = False
        # PO-063/RN-039: Campo base so pode ser outro Campo tipo Data — o
        # form ja restringe a lista para reduzir erro de cadastro; a
        # validacao de "mesmo Setor" fica em clean() (depende do valor
        # escolhido em setor_nome, so disponivel apos o submit).
        self.fields['campo_base'].required = False
        self.fields['campo_base'].queryset = Campo.objects.filter(tipo=Campo.TIPO_DATA).order_by('setor_nome', 'nome')
        if self.instance.pk:
            self.fields['campo_base'].queryset = self.fields['campo_base'].queryset.exclude(pk=self.instance.pk)

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        setor_nome = cleaned_data.get('setor_nome')
        opcoes = [linha.strip() for linha in cleaned_data.get('opcoes_texto', '').splitlines() if linha.strip()]

        if tipo == Campo.TIPO_LISTA and not opcoes:
            self.add_error('opcoes_texto', "Informe pelo menos uma opção para o tipo Lista.")

        if tipo == Campo.TIPO_CALCULADO:
            campo_base = cleaned_data.get('campo_base')
            horas_prazo = cleaned_data.get('horas_prazo')
            if not campo_base:
                self.add_error('campo_base', "Selecione o Campo base para o tipo Calculado.")
            elif campo_base.tipo != Campo.TIPO_DATA:
                self.add_error('campo_base', "O Campo base precisa ser do tipo Data.")
            elif setor_nome and campo_base.setor_nome != setor_nome:
                self.add_error('campo_base', "O Campo base precisa pertencer ao mesmo Setor do campo calculado.")
            if not horas_prazo or horas_prazo <= 0:
                self.add_error('horas_prazo', "Informe um número positivo de horas de prazo.")

        cleaned_data['opcoes'] = opcoes
        return cleaned_data

    def _post_clean(self):
        # "opcoes" nao e campo do form (usa "opcoes_texto"); precisa estar no
        # instance antes de Model.full_clean() rodar, senao Campo.clean()
        # valida a lista vazia default do model, nao o valor digitado.
        self.instance.opcoes = self.cleaned_data.get('opcoes', [])
        super()._post_clean()

    def save(self, commit=True):
        campo = super().save(commit=False)
        campo.opcoes = self.cleaned_data.get('opcoes', [])
        if commit:
            campo.save()
        return campo


class CampoObrigatoriedadeTransicaoForm(forms.ModelForm):
    """PO-079/RN-061/ADR-031: regra de obrigatoriedade de um Campo
    (RN-031) ao trocar para outro Setor. `setor_destino_nome` usa o mesmo
    vocabulario ja cadastrado em `Setor.nome` (RN-025), oferecido como
    lista — mesmo padrao ja usado em `CampoForm.setor_nome`. O Setor de
    origem da regra e sempre o Setor dono do Campo (`campo.setor_nome`),
    por isso nao entra como opcao de destino."""

    setor_destino_nome = forms.ChoiceField(label="Setor de destino")

    class Meta:
        model = CampoObrigatoriedadeTransicao
        fields = ['setor_destino_nome']

    def __init__(self, *args, campo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.campo = campo
        nomes_setor = Setor.objects.order_by('nome').values_list('nome', flat=True)
        nomes_destino = [
            nome for nome in dict.fromkeys(nomes_setor) if not campo or nome != campo.setor_nome
        ]
        self.fields['setor_destino_nome'].choices = [(nome, nome) for nome in nomes_destino]

    def clean_setor_destino_nome(self):
        nome = self.cleaned_data['setor_destino_nome']
        if self.campo and nome == self.campo.setor_nome:
            raise forms.ValidationError("O Setor de destino não pode ser igual ao Setor dono do Campo.")
        return nome


class ExcelUploadForm(forms.Form):
    file = forms.FileField(label="Selecione a Planilha (.xlsx ou .csv)")


class BackupRestoreForm(forms.Form):
    backup_existente = forms.ChoiceField(
        required=False,
        label="Selecione um backup ja salvo no servidor",
    )
    file = forms.FileField(label="Selecione o backup (.zip)", required=False)
    confirmar = forms.BooleanField(
        required=True,
        label="Confirmo que este restore vai substituir os dados atuais",
    )

    def __init__(self, *args, backup_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["backup_existente"].choices = [("", "Selecione um backup do servidor")] + list(backup_choices or [])

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("backup_existente") and not cleaned_data.get("file"):
            raise forms.ValidationError("Selecione um backup do servidor ou envie um arquivo .zip.")
        return cleaned_data


class SMTPTestForm(forms.Form):
    from_email = forms.EmailField(
        label="Remetente",
        required=False,
        help_text="Se ficar vazio, usamos o remetente padrao do sistema. Para caixa compartilhada no Microsoft 365, autentique com a conta SMTP e informe aqui o e-mail da caixa com permissao 'Enviar como'.",
    )
    to_email = forms.CharField(
        label="Destinatario",
        help_text="Aceita um ou mais e-mails separados por virgula ou ponto e virgula.",
    )
    cc_email = forms.CharField(
        label="Cc",
        required=False,
        help_text="Opcional. Aceita multiplos e-mails separados por virgula ou ponto e virgula.",
    )
    subject = forms.CharField(label="Assunto", max_length=200)
    body = forms.CharField(label="Mensagem", widget=forms.Textarea(attrs={"rows": 10}))
