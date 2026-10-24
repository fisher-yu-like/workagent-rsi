"""Keep fixed qualification implementations out of formal result paths."""


def require_production(*components):
    for component in components:
        if getattr(component,'qualification_only',False):
            raise ValueError('formal execution rejects qualification_only component: '+getattr(component,'__name__',type(component).__name__))
