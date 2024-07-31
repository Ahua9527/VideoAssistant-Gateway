import sys
import subprocess
import time
import NDIlib as ndi
import logging
import argparse

def initialize_ndi():
    if not ndi.initialize():
        logging.error("无法初始化NDI库")
        sys.exit(1)

def find_ndi_sources():
    find_instance = ndi.find_create_v2()
    if not find_instance:
        logging.error("无法创建NDI查找实例")
        sys.exit(1)

    logging.info("正在查找NDI源...")
    time.sleep(2)
    sources = ndi.find_get_current_sources(find_instance)
    if not sources:
        logging.error("未找到NDI源")
        sys.exit(1)
    return find_instance, sources

def select_ndi_source(sources):
    for i, source in enumerate(sources):
        print(f"{i}: {source.ndi_name}")

    while True:
        try:
            source_index = int(input("选择NDI源的索引 (默认0): ") or 0)
            if 0 <= source_index < len(sources):
                return sources[source_index]
            else:
                logging.warning("无效的索引，请重新输入。")
        except ValueError:
            logging.warning("请输入有效的数字索引")

def create_ndi_receiver(source):
    recv_create_desc = ndi.RecvCreateV3()
    recv_create_desc.source_to_connect_to = source
    recv_instance = ndi.recv_create_v3(recv_create_desc)
    if not recv_instance:
        logging.error("无法创建NDI接收器")
        sys.exit(1)
    ndi.recv_connect(recv_instance, source)
    return recv_instance

def get_video_info(recv_instance):
    time.sleep(1)
    while True:
        t, v, a, m = ndi.recv_capture_v2(recv_instance, timeout_in_ms=5000)
        if t == ndi.FRAME_TYPE_VIDEO:
            width = v.xres
            height = v.yres
            framerate = round(v.frame_rate_N / v.frame_rate_D)
            pixel_format = v.FourCC
            ndi.recv_free_video_v2(recv_instance, v)  # 释放NDI视频帧
            return width, height, framerate, pixel_format

def start_ffmpeg_process(video_resolution, frame_rate, srt_server_url, video_bitrate="2000k", buffer_size="3000k"):
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
        "-color_range", "mpeg",
        "-f", "mpegts",
        srt_server_url
    ]
    return subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="NDI to SRT streaming")
    parser.add_argument("srt_server_url", help="SRT服务器的URL")
    args = parser.parse_args()

    srt_server_url = args.srt_server_url

    initialize_ndi()
    find_instance, sources = find_ndi_sources()
    source = select_ndi_source(sources)
    recv_instance = create_ndi_receiver(source)
    
    width, height, framerate, pixel_format = get_video_info(recv_instance)
    video_resolution = f"{width}x{height}"
    frame_rate = str(framerate)
    
    ffmpeg_process = start_ffmpeg_process(video_resolution, frame_rate, srt_server_url)

    try:
        while True:
            t, v, a, m = ndi.recv_capture_v2(recv_instance, timeout_in_ms=5000)
            if t == ndi.FRAME_TYPE_VIDEO:
                ffmpeg_process.stdin.write(v.data)
                ndi.recv_free_video_v2(recv_instance, v)  # 释放NDI视频帧
            # 捕获FFmpeg的输出
            if ffmpeg_process.poll() is not None:
                logging.error("FFmpeg进程已意外终止")
                break

        stdout, stderr = ffmpeg_process.communicate()
        logging.info(stdout.decode())
        logging.error(stderr.decode())

    except KeyboardInterrupt:
        logging.info("捕获到中断信号，正在停止...")
    except Exception as e:
        logging.error(f"发生错误: {e}")
    finally:
        if recv_instance:
            ndi.recv_destroy(recv_instance)
        if find_instance:
            ndi.find_destroy(find_instance)
        if ffmpeg_process:
            ffmpeg_process.stdin.close()
            ffmpeg_process.wait()
        logging.info("FFmpeg进程已关闭，资源释放完成")

if __name__ == "__main__":
    main()