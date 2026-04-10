from django import forms


class ExcelUploadForm(forms.Form):
    file = forms.FileField(label="Selecione a Planilha (.xlsx ou .csv)")


class BackupRestoreForm(forms.Form):
    file = forms.FileField(label="Selecione o backup (.zip)")
    confirmar = forms.BooleanField(
        required=True,
        label="Confirmo que este restore vai substituir os dados atuais",
    )
