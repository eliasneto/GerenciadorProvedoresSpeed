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
