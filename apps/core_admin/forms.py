from django import forms

class ExcelUploadForm(forms.Form):
    file = forms.FileField(label="Selecione a Planilha (.xlsx ou .csv)")