import subprocess, shutil, os, sys

print(f"Python: {sys.version}")
print(f"os.environ PATH:")
for p in os.environ.get('PATH', '').split(';'):
    if 'miktex' in p.lower() or 'Miktex' in p:
        print(f"  FOUND: {p}")

print()
print("=== Checking MiKTeX directly ===")
miktex_bin = r"D:\Miktex\miktex\bin\x64"
latex_exe = os.path.join(miktex_bin, "latex.exe")
print(f"  latex.exe exists: {os.path.exists(latex_exe)}")

# Add to PATH for this process
if miktex_bin not in os.environ['PATH']:
    os.environ['PATH'] = os.environ['PATH'] + ';' + miktex_bin
    print(f"  Added {miktex_bin} to process PATH")

print()
print("=== Re-checking after PATH update ===")
for cmd in ['latex', 'pdflatex', 'xelatex']:
    path = shutil.which(cmd)
    print(f"  {cmd}: {path or 'NOT FOUND'}")

# Test actual LaTeX compilation
print()
print("=== Test LaTeX compilation ===")
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    tex_file = os.path.join(tmpdir, "test.tex")
    with open(tex_file, 'w') as f:
        f.write(r"\documentclass{article}\begin{document}Hello $\angle A = 60^\circ$\end{document}")
    
    try:
        result = subprocess.run(
            ['latex', '-interaction=nonstopmode', '-output-directory', tmpdir, tex_file],
            capture_output=True, text=True, timeout=30,
            env=os.environ  # Pass updated env
        )
        print(f"  exit code: {result.returncode}")
        dvi_file = os.path.join(tmpdir, "test.dvi")
        print(f"  DVI created: {os.path.exists(dvi_file)}")
        if result.returncode != 0:
            # Show last few lines of stderr/stdout
            lines = (result.stdout + result.stderr).split('\n')
            for line in lines[-5:]:
                if line.strip():
                    print(f"  {line.strip()}")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

# Test Manim MathTex
print()
print("=== Manim MathTex test ===")
try:
    from manim import MathTex, tempconfig
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempconfig({"output_file": "test_manim", "media_dir": tmpdir}):
            try:
                m = MathTex(r"\angle A + \angle B + \angle C = 180^\circ")
                print("  MathTex creation: SUCCESS")
            except Exception as e:
                print(f"  MathTex FAILED: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  Setup error: {type(e).__name__}: {e}")
