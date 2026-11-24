"""rc25a: a single persistent literal field, not an LLM passthrough."""
import importlib.util
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
name = "h3_prompt_composer_rc25_recipe"
spec = importlib.util.spec_from_file_location(
    name, PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)]
)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
nodes = sys.modules[name + ".nodes"]


class RecipePromptTests(unittest.TestCase):
    def test_single_literal_input_is_obvpm_recipe_compatible(self):
        cls = nodes.H3DirectorRecipePrompt
        schema = cls.INPUT_TYPES()
        self.assertEqual(set(schema), {"required"})
        self.assertEqual(list(schema["required"]), ["prompt_text"])
        widget_type, opts = schema["required"]["prompt_text"]
        self.assertEqual(widget_type, "STRING")
        self.assertTrue(opts["multiline"])
        self.assertFalse(opts.get("forceInput", False))
        self.assertEqual(cls.RETURN_TYPES, ("STRING",))
        self.assertEqual(cls.RETURN_NAMES, ("prompt",))
        self.assertFalse(getattr(cls, "OUTPUT_NODE", False))
        self.assertNotIn("IS_CHANGED", cls.__dict__)
        self.assertEqual(nodes.NODE_CLASS_MAPPINGS["H3DirectorRecipePrompt"], cls)

    def test_exact_text_and_manual_edit_preserved(self):
        prompt = "subject_definitions:\n<Subject 1> is Farrah.\n\n<d>[English] Hi!</d>\n"
        node = nodes.H3DirectorRecipePrompt()
        self.assertEqual(node.emit(prompt), (prompt,))
        self.assertEqual(node.emit(prompt + "  "), (prompt + "  ",))

    def test_portable_example_is_split_into_workspace_and_one_restore_prompt(self):
        import json
        example = json.loads((PACKAGE / "examples/H3-Director-Core-Workspace.json").read_text())
        groups = {g["title"]: g for g in example["groups"]}
        self.assertIn("Director Inputs", groups)
        self.assertIn("Director Prompt [restore]", groups)
        recipe = [n for n in example["nodes"] if n["type"] == "H3DirectorRecipePrompt"]
        self.assertEqual(len(recipe), 1)
        node = recipe[0]
        x,y = node["pos"]
        w,h = node["size"]
        gx,gy,gw,gh = groups["Director Prompt [restore]"]["bounding"]
        self.assertTrue(gx <= x and gy <= y and x+w <= gx+gw and y+h <= gy+gh)
        self.assertEqual([i["name"] for i in node["inputs"]], ["prompt_text"])
        self.assertEqual([o["name"] for o in node["outputs"]], ["prompt"])
        self.assertEqual(node["outputs"][0]["links"], [])
        other = [n for n in example["nodes"] if n["id"] != node["id"]]
        self.assertTrue(all(n["pos"][0]+n["size"][0] < gx for n in other))
        self.assertGreaterEqual(example["last_node_id"], max(n["id"] for n in example["nodes"]))
        ids = {n["id"] for n in example["nodes"]}
        self.assertTrue(all(l[1] in ids and l[3] in ids for l in example["links"]))

    def test_empty_prompt_fails_closed(self):
        node = nodes.H3DirectorRecipePrompt()
        for invalid in ["", "  \n"]:
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "empty"):
                    node.emit(invalid)


if __name__ == "__main__":
    unittest.main()
