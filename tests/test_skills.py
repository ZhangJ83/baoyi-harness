import unittest

from agent.skills import Skill, match


class SkillTests(unittest.TestCase):
    def test_progressive_matching_avoids_generic_create(self):
        skill = Skill("powerpoint", "Create, modify, render PPT and PowerPoint slide decks", "body", None)
        self.assertEqual(match("create a Python parser", [skill]), [])
        self.assertEqual(match("render this PPT slide deck", [skill]), [skill])

    def test_skill_metadata_can_constrain_tools(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from agent.skills import _parse
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo" / "SKILL.md"
            path.parent.mkdir()
            path.write_text("---\nname: demo\ndescription: Demo skill\nwhen_to_use: For demos\nallowed_tools: [read_file, ppt_verify]\n---\nbody", encoding="utf-8")
            skill = _parse(path)
        self.assertEqual(skill.when_to_use, "For demos")
        self.assertEqual(skill.allowed_tools, ("read_file", "ppt_verify"))


if __name__ == "__main__":
    unittest.main()
