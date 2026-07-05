import subprocess, shutil, os, sys

print(f"Python: {sys.version}")
print(f"PATH has miktex: {'miktex' in os.environ.get('PATH', '').lower()}")
print()

# Check if latex is findable via shutil.which
print("=== LaTeX commands on PATH ===")
for cmd in ['latex', 'pdflatex', 'xelatex', 'lualatex']:
    path = shutil.which(cmd)
    print(f"  {cmd}: {path or 'NOT FOUND'}")

# Try running latex --version
print()
print("=== latex --version ===")
try:
    result = subprocess.run(['latex', '--version'], capture_output=True, text=True, timeout=10)
    print(f"  exit code: {result.returncode}")
    first_line = result.stdout.split('\n')[0] if result.stdout else '(no stdout)'
    print(f"  output: {first_line}")
except Exception as e:
    print(f"  FAILED: {e}")

# Check Manim
print()
print("=== Manim availability ===")
try:
    import manim
    print(f"  manim version: {manim.__version__}")
except ImportError:
    print("  manim NOT installed in this env")

# Test MathTex
print()
print("=== MathTex test ===")
try:
    from manim import MathTex, Tex, Scene, tempconfig
    # Just test if MathTex can be instantiated (requires LaTeX)
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempconfig({"output_file": "test_latex", "media_dir": tmpdir}):
            try:
                m = MathTex(r"\angle A + \angle B + \angle C = 180^\circ")
                print("  MathTex creation: SUCCESS")
                print(f"  MathTex string: {m.get_string() if hasattr(m, 'get_string') else 'N/A'}")
            except Exception as e:
                print(f"  MathTex creation FAILED: {type(e).__name__}: {e}")
except ImportError as e:
    print(f"  manim import failed: {e}")
except Exception as e:
    print(f"  Error: {type(e).__name__}: {e}")
