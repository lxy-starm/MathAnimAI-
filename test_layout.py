"""
综合布局测试脚本 — 测试多种题型，验证无空屏且布局合理
"""
import sys
import os
import json
import tempfile

# 设置项目路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# 使用临时目录作为输出，避免沙箱权限问题
TEMP_OUTPUT = tempfile.mkdtemp(prefix="mathanim_layout_")
os.environ["OUTPUT_DIR"] = TEMP_OUTPUT

from parser.schema import (
    ProblemScript, ProblemType, Step, AnimationType,
    GeoElement, CoordinateConfig, AnimationSettings,
)

# ================================================================
# 测试1：几何题（三角形 + 辅助线 + 角度标注）
# ================================================================
def make_geometry_script():
    return ProblemScript(
        problem_type=ProblemType.GEOMETRY,
        grade_level="初中",
        problem_text="已知三角形ABC中，角C=90度，AC=3，BC=4，求AB的长",
        final_answer="AB=5",
        settings=AnimationSettings(duration=1.0),
        base_figure=GeoElement(
            type="triangle",
            points=[[-2, -1, 0], [2, -1, 0], [0, 2, 0]],
            labels=["A", "B", "C"],
        ),
        steps=[
            Step(
                step_number=1,
                title="已知条件",
                text="在直角三角形ABC中，角C等于90度",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                voice_text="在直角三角形ABC中，角C等于90度",
            ),
            Step(
                step_number=2,
                title="标注直角",
                text="角C是直角",
                animation_type=AnimationType.MARK_RIGHT_ANGLE,
                config={
                    "vertex": [0, 2, 0],
                    "point_a": [-2, -1, 0],
                    "point_b": [2, -1, 0],
                },
                voice_text="角C是直角",
            ),
            Step(
                step_number=3,
                title="应用勾股定理",
                text="根据勾股定理，AC平方加BC平方等于AB平方",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                math_expr="3^2 + 4^2 = AB^2",
                voice_text="根据勾股定理，AC平方加BC平方等于AB平方",
            ),
            Step(
                step_number=4,
                title="计算结果",
                text="9加16等于25，所以AB等于5",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                math_expr="AB = \\sqrt{25} = 5",
                voice_text="9加16等于25，所以AB等于5",
            ),
        ],
    )


# ================================================================
# 测试2：方程题（多步推导）
# ================================================================
def make_equation_script():
    return ProblemScript(
        problem_type=ProblemType.EQUATION,
        grade_level="初中",
        problem_text="解方程：2x + 5 = 13",
        final_answer="x = 4",
        settings=AnimationSettings(duration=1.0),
        steps=[
            Step(
                step_number=1,
                title="移项",
                text="将常数项移到等号右边",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                math_expr="2x = 13 - 5",
                voice_text="将常数项移到等号右边",
            ),
            Step(
                step_number=2,
                title="化简",
                text="计算右边得到8",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                math_expr="2x = 8",
                voice_text="计算右边得到8",
            ),
            Step(
                step_number=3,
                title="求解",
                text="两边同除以2",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                math_expr="x = 4",
                voice_text="两边同除以2，得到x等于4",
            ),
        ],
    )


# ================================================================
# 测试3：函数题（坐标系 + 函数曲线）
# ================================================================
def make_function_script():
    return ProblemScript(
        problem_type=ProblemType.FUNCTION,
        grade_level="初中",
        problem_text="画出函数 y = x^2 的图像",
        final_answer="抛物线，开口向上",
        settings=AnimationSettings(duration=1.0),
        coordinate_system=CoordinateConfig(
            x_range=[-5, 5, 1],
            y_range=[-2, 10, 2],
            x_length=9,
            y_length=6,
        ),
        steps=[
            Step(
                step_number=1,
                title="建立坐标系",
                text="首先建立平面直角坐标系",
                animation_type=AnimationType.PLOT_COORDINATE,
                config={
                    "x_range": [-5, 5, 1],
                    "y_range": [-2, 10, 2],
                    "x_length": 9.0,
                    "y_length": 6.0,
                },
                voice_text="首先建立平面直角坐标系",
            ),
            Step(
                step_number=2,
                title="绘制函数",
                text="画出y等于x平方的图像",
                animation_type=AnimationType.PLOT_FUNCTION,
                math_expr="x**2",
                config={"function": "x**2"},
                voice_text="画出y等于x平方的图像",
            ),
            Step(
                step_number=3,
                title="标注顶点",
                text="抛物线的顶点在原点",
                animation_type=AnimationType.PLOT_POINT,
                config={"point": [0, 0]},
                voice_text="抛物线的顶点在原点",
            ),
        ],
    )


# ================================================================
# 测试4：分数题（饼图）
# ================================================================
def make_fraction_script():
    return ProblemScript(
        problem_type=ProblemType.FRACTION,
        grade_level="小学",
        problem_text="用饼图表示分数 1/4",
        final_answer="1/4",
        settings=AnimationSettings(duration=1.0),
        steps=[
            Step(
                step_number=1,
                title="题目",
                text="用饼图表示分数四分之一",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                voice_text="用饼图表示分数四分之一",
            ),
            Step(
                step_number=2,
                title="绘制饼图",
                text="将圆分成4份，取其中1份",
                animation_type=AnimationType.DRAW_PIE_CHART,
                config={
                    "values": [1, 3],
                    "labels": ["1/4", "3/4"],
                },
                voice_text="将圆分成4份，取其中1份",
            ),
            Step(
                step_number=3,
                title="结果",
                text="阴影部分表示四分之一",
                animation_type=AnimationType.TEXT_SLIDE_IN,
                voice_text="阴影部分表示四分之一",
            ),
        ],
    )


# ================================================================
# 运行测试
# ================================================================
def run_test(name, script, audio_durations=None, audio_paths=None):
    """渲染单个测试"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")

    from animation.builder import build_and_render, generate_scene_code

    # 先生成代码并打印，检查是否有明显问题
    code = generate_scene_code(script, audio_durations=audio_durations, audio_paths=audio_paths)
    print(f"\n--- 生成的代码（前20行）---")
    for line in code.split('\n')[:20]:
        print(f"  {line}")
    print(f"  ...")

    # 渲染
    try:
        video_path = build_and_render(
            script,
            hd=True,
            audio_durations=audio_durations,
            audio_paths=audio_paths,
        )
        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path)
            print(f"\n[PASS] 渲染成功: {video_path}")
            print(f"   文件大小: {file_size / 1024:.1f} KB")
            return video_path
        else:
            print(f"\n[FAIL] 渲染失败: 未生成视频文件")
            return None
    except Exception as e:
        print(f"\n[FAIL] 渲染异常: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    results = {}

    # 测试1：几何题
    script1 = make_geometry_script()
    durations1 = {1: 3.0, 2: 2.0, 3: 4.0, 4: 3.5}
    results["geometry"] = run_test("几何题（三角形+直角标注+勾股定理）", script1, audio_durations=durations1)

    # 测试2：方程题
    script2 = make_equation_script()
    durations2 = {1: 3.0, 2: 2.5, 3: 3.0}
    results["equation"] = run_test("方程题（2x+5=13）", script2, audio_durations=durations2)

    # 测试3：函数题
    script3 = make_function_script()
    durations3 = {1: 3.0, 2: 4.0, 3: 2.5}
    results["function"] = run_test("函数题（y=x^2）", script3, audio_durations=durations3)

    # 测试4：分数题
    script4 = make_fraction_script()
    durations4 = {1: 3.0, 2: 4.0, 3: 3.0}
    results["fraction"] = run_test("分数题（饼图1/4）", script4, audio_durations=durations4)

    # 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")
    for name, path in results.items():
        status = "[PASS]" if path else "[FAIL]"
        print(f"  {name}: {status}")

    # 复制成功的视频到工作目录
    output_dir = r"C:\Users\lxy\WorkBuddy\2026-07-04-12-13-00\output"
    os.makedirs(output_dir, exist_ok=True)
    import shutil
    for name, path in results.items():
        if path:
            dest = os.path.join(output_dir, f"test_layout_{name}.mp4")
            try:
                shutil.copy2(path, dest)
                print(f"  已复制: {dest}")
            except Exception as e:
                print(f"  复制失败 ({name}): {e}")
