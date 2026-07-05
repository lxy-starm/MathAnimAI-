"""Final verification: simulate user running main.py from conda env"""
import sys, os, shutil

print("=" * 60)
print("LaTeX / MathTex Final Verification")
print("=" * 60)

# Step 1: Check config.py auto-detection
print("\n[1] Importing config (auto-detect LaTeX)...")
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from config import FONT_FAMILY
print(f"    FONT_FAMILY = {FONT_FAMILY}")

# Step 2: Verify LaTeX on PATH
print("\n[2] LaTeX commands on PATH:")
for cmd in ['latex', 'pdflatex', 'xelatex', 'dvisvgm']:
    path = shutil.which(cmd)
    print(f"    {cmd}: {path or 'NOT FOUND'}")

# Step 3: Test Manim MathTex with various math symbols
print("\n[3] Testing MathTex with various formulas...")
from manim import MathTex, Tex, tempconfig
import tempfile

test_formulas = [
    (r"\angle A + \angle B + \angle C = 180^\circ", "Triangle angles"),
    (r"S = \pi r^2", "Circle area"),
    (r"a^2 + b^2 = c^2", "Pythagorean"),
    (r"\sqrt{9} = 3", "Square root"),
    (r"x \leq 5, \quad x \geq -5", "Inequalities"),
    (r"\frac{a}{b} \times \frac{c}{d}", "Fractions"),
]

with tempfile.TemporaryDirectory() as tmpdir:
    with tempconfig({"output_file": "verify", "media_dir": tmpdir}):
        for formula, desc in test_formulas:
            try:
                m = MathTex(formula)
                print(f"    OK  {desc}: {formula}")
            except Exception as e:
                print(f"    FAIL {desc}: {type(e).__name__}: {e}")

# Step 4: Test Tex (text mode LaTeX)
print("\n[4] Testing Tex (text mode)...")
tex_tests = [
    (r"三角形内角和", "Chinese text"),
    (r"Area $= \pi r^2$", "Mixed text+math"),
]
with tempfile.TemporaryDirectory() as tmpdir:
    with tempconfig({"output_file": "verify_tex", "media_dir": tmpdir}):
        for tex_str, desc in tex_tests:
            try:
                t = Tex(tex_str)
                print(f"    OK  {desc}: {tex_str}")
            except Exception as e:
                print(f"    FAIL {desc}: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Verification COMPLETE")
print("=" * 60)
