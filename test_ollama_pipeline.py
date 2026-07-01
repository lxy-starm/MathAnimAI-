"""Test Ollama full pipeline — standalone script"""
import sys, os, time, logging
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logging.getLogger('manim').setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)

from main import run_full_pipeline, _is_llm_available

print('[1] Health check...')
ok = _is_llm_available()
print(f'    Ollama available: {ok}')

print('[2] Running full pipeline (word problem)...')
start = time.time()
result = run_full_pipeline(
    problem_text='小明有12个苹果，吃了3个，又买了5个，现在有多少个？',
    grade_level='小学',
    problem_type='应用题',
)
elapsed = time.time() - start

print()
print('=' * 60)
print('OLLAMA PIPELINE RESULT')
print('=' * 60)
print(f'Success: {result["success"]}')
print(f'Steps: {len(result["steps"])}')
for s in result['steps']:
    print(f'  [{s["step_number"]}] {s["title"]}: {s["text"][:80]}')
print(f'Message: {result["message"][:200]}')
print(f'Video: {result["video_path"]}')
if result['video_path'] and os.path.exists(result['video_path']):
    print(f'Video size: {os.path.getsize(result["video_path"])/1024/1024:.2f} MB')
print(f'Total: {elapsed:.1f}s')
print()
print('[3] Test 2: Geometry...')
result2 = run_full_pipeline(
    problem_text='已知直角三角形的两条直角边分别为3cm和4cm，求斜边长',
    grade_level='初中',
    problem_type='几何',
)
elapsed2 = time.time() - start - elapsed
print(f'Success: {result2["success"]}')
print(f'Steps: {len(result2["steps"])}')
for s in result2['steps']:
    print(f'  [{s["step_number"]}] {s["title"]}: {s["text"][:80]}')
print(f'Video: {result2["video_path"]}')
if result2['video_path'] and os.path.exists(result2['video_path']):
    print(f'Video size: {os.path.getsize(result2["video_path"])/1024/1024:.2f} MB')
print(f'Total test 2: {elapsed2:.1f}s')
