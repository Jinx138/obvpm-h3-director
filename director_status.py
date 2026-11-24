"""A transparent validation tap; never an independent execution target."""
class H3DirectorStatus:
    CATEGORY = "obvpm/director"
    FUNCTION = "inspect"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("validation",)
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"validation": ("STRING", {"forceInput": True})}}
    def inspect(self, validation):
        return {"ui": {"director_status": [str(validation)]}, "result": (validation,)}
