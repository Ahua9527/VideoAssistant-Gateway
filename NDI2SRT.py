import sys
import subprocess
import time
import NDIlib as ndi

# 初始化NDI库
if not ndi.initialize():
    print("无法初始化NDI库")
    sys.exit(1)

# 查找NDI源
find_instance = ndi.find_create_v2()
if not find_instance:
    print("无法创建NDI查找实例")
    sys.exit(1)

print("正在查找NDI源...")
time.sleep(2)  # 等待一段时间以便查找源
sources = ndi.find_get_current_sources(find_instance)
if not sources:
    print("未找到NDI源")
    sys.exit(1)

# 打印找到的NDI源
for i, source in enumerate(sources):
    print(f"{i}: {source.ndi_name}")

# 选择NDI源
try:
    source_index = int(input("选择NDI源的索引: "))
    if source_index < 0 or source_index >= len(sources):
        print("无效的索引")
        sys.exit(1)
except ValueError:
    print("请输入有效的数字索引")
    sys.exit(1)

# 创建NDI接收器
recv_create_desc = ndi.RecvCreateV3()
recv_create_desc.source_to_connect_to = sources[source_index]
recv_instance = ndi.recv_create_v3(recv_create_desc)
if not recv_instance:
    print("无法创建NDI接收器")
    sys.exit(1)

ndi.recv_connect(recv_instance, sources[source_index])

# 获取视频流信息
time.sleep(1)  # 等待一段时间以便接收器能够连接到源并获取视频流信息

# 获取第一帧视频，提取分辨率和帧率
while True:
    t, v, a, m = ndi.recv_capture_v2(recv_instance, timeout_in_ms=5000)
    if t == ndi.FRAME_TYPE_VIDEO:
        width = v.xres
        height = v.yres
        framerate = round(v.frame_rate_N / v.frame_rate_D)
        break

# 配置参数
srt_server_url = "srt://你的srt推流地址"
video_resolution = f"{width}x{height}"
frame_rate = str(framerate)
video_bitrate = "2500k"
buffer_size = "5000k"

# FFmpeg命令，将NDI流传输到SRT服务器
ffmpeg_command = [
    "ffmpeg",
    "-f", "rawvideo",
    "-pixel_format", "uyvy422",
    "-video_size", video_resolution,
    "-framerate", frame_rate,
    "-i", "-",
    "-c:v", "h264_videotoolbox",
    "-b:v", video_bitrate,
    "-maxrate", video_bitrate,
    "-bufsize", buffer_size,
    "-f", "mpegts",
    srt_server_url
]

# 创建FFmpeg进程
ffmpeg_process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

try:
    while True:
        # 获取视频帧
        t, v, a, m = ndi.recv_capture_v2(recv_instance, timeout_in_ms=5000)
        if t == ndi.FRAME_TYPE_VIDEO:
            ffmpeg_process.stdin.write(v.data)
finally:
    # 关闭NDI接收器
    ndi.recv_destroy(recv_instance)
    ndi.find_destroy(find_instance)
    ffmpeg_process.stdin.close()
    ffmpeg_process.wait()
