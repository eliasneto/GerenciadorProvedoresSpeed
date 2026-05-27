from rest_framework.schemas.openapi import AutoSchema


class IntegracoesApiSchema(AutoSchema):
    def _pluralize(self, value):
        lowered = value.lower()
        if lowered.endswith("s"):
            return value
        if lowered.endswith(("ch", "sh", "x", "z")):
            return f"{value}es"
        if lowered.endswith("y") and len(value) > 1 and lowered[-2] not in "aeiou":
            return f"{value[:-1]}ies"
        return f"{value}s"

    def get_operation_id_base(self, path, method, action):
        model = getattr(getattr(self.view, "queryset", None), "model", None)

        if self.operation_id_base is not None:
            name = self.operation_id_base
        elif model is not None:
            name = model.__name__
        elif self.get_serializer(path, method) is not None:
            name = self.get_serializer(path, method).__class__.__name__
            if name.endswith("Serializer"):
                name = name[:-10]
        else:
            name = self.view.__class__.__name__
            if name.endswith("APIView"):
                name = name[:-7]
            elif name.endswith("View"):
                name = name[:-4]

            if name.endswith(action.title()):
                name = name[:-len(action)]

        if action == "list":
            name = self._pluralize(name)

        return name
