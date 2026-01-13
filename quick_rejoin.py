"""
快速重新拼接视频，不重新检测击杀
使用已有的clips，只重新执行join和audio阶段
"""
import os
import glob
from src.config.config_loader import ConfigLoader
from src.video.video_joiner import VideoJoiner
from src.audio.audio_mixer import AudioMixer

# 配置
video_basename = "Battlefield 6 2026.01.12 - 22.49.03.14"
pipeline_dir = "temp/pipeline_4f47eb1e"  # 最新的pipeline目录
output_dir = "G:/Video/Battlefield 6/my_highlights"

# 加载配置
config_loader = ConfigLoader()
config = config_loader.load_config('battlefield6')

# 1. 找到所有clips
clips_dir = os.path.join(pipeline_dir, "clips")
clip_files = sorted(glob.glob(os.path.join(clips_dir, "clip_*.mp4")))

print(f"找到 {len(clip_files)} 个clips:")
for clip in clip_files:
    print(f"  - {os.path.basename(clip)}")

if not clip_files:
    print("错误：没有找到clips!")
    exit(1)

# 2. 拼接clips（使用xfade转场）
joined_video = os.path.join(pipeline_dir, "joined_no_audio.mp4")
print(f"\n开始拼接，使用转场类型: {config['highlights'].get('transition_type', 'random')}")

joiner = VideoJoiner(config)
success = joiner.join_clips(clip_files, joined_video)

if not success:
    print("拼接失败!")
    exit(1)

print(f"✓ 拼接完成: {joined_video}")

# 3. 混音
final_video = os.path.join(output_dir, f"{video_basename}_highlights.mp4")
os.makedirs(output_dir, exist_ok=True)

print(f"\n开始混音...")
mixer = AudioMixer(config)
result = mixer.mix_audio(joined_video, final_video)

if result == joined_video:
    # 音乐禁用，复制文件
    import shutil
    shutil.copy2(joined_video, final_video)
    print(f"✓ 已复制（无音乐）: {final_video}")
else:
    print(f"✓ 混音完成: {final_video}")

print("\n完成！")
