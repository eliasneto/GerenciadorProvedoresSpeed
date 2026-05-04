from django import forms


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
